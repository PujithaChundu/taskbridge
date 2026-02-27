from flask import Flask, render_template, request, redirect, session, send_from_directory, flash
import os
import psycopg2
import requests
import secrets
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "taskbridge-secret-key")

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "TASKBRIDGE-ADMIN-2024")

# =========================
# DATABASE
# =========================
def get_db_connection():
    return psycopg2.connect(os.getenv("DATABASE_URL"))

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email TEXT UNIQUE,
            password TEXT,
            role TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id SERIAL PRIMARY KEY,
            title TEXT,
            description TEXT,
            end_date TEXT,
            status TEXT,
            assigned_to TEXT,
            created_by TEXT,
            attachment TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS password_resets (
            id SERIAL PRIMARY KEY,
            email TEXT,
            token TEXT,
            expires_at TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

init_db()

# =========================
# EMAIL
# =========================
def send_email(to_email, subject, html_content):
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        print("RESEND_API_KEY missing")
        return

    url = "https://api.resend.com/emails"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "from": "TaskBridge <onboarding@resend.dev>",
        "to": [to_email],
        "subject": subject,
        "html": html_content
    }

    response = requests.post(url, json=data, headers=headers)
    print("Email response:", response.text)

def send_task_assignment_email(to_email, title, description, end_date):
    html = f"""
    <h3>New Task Assigned</h3>
    <p><b>Title:</b> {title}</p>
    <p><b>Description:</b> {description}</p>
    <p><b>Deadline:</b> {end_date}</p>
    """
    send_email(to_email, "New Task Assigned - TaskBridge", html)

# =========================
# LOGIN
# =========================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM users WHERE email=%s AND password=%s", (email, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session["user_email"] = email
            session["user_role"] = user[0]
            return redirect("/admin-dashboard" if user[0] == "admin" else "/user-dashboard")

        flash("Invalid email or password")
        return redirect("/")

    return render_template("login.html")

# =========================
# SIGNUP
# =========================
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]
        admin_key = request.form.get("admin_key")

        if role == "admin" and admin_key != ADMIN_SECRET_KEY:
            flash("Invalid Admin Secret Key")
            return redirect("/signup")

        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (email, password, role) VALUES (%s, %s, %s)",
                (email, password, role)
            )
            conn.commit()
            conn.close()

            send_email(email, "Welcome to TaskBridge!",
                       f"<p>Welcome! You signed up as <b>{role}</b>.</p>")

            flash("Account created successfully!")
            return redirect("/")
        except:
            flash("Email already registered")
            return redirect("/signup")

    return render_template("signup.html")

# =========================
# CREATE TASK (ADMIN)
# =========================
@app.route("/create-task", methods=["GET", "POST"])
def create_task():
    if session.get("user_role") != "admin":
        return redirect("/")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM users WHERE role='user'")
    employees = cursor.fetchall()

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        end_date = request.form["end_date"]
        assigned_to = request.form["assigned_to"]

        cursor.execute("""
            INSERT INTO tasks (title, description, end_date, status, assigned_to, created_by)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (title, description, end_date, "Pending", assigned_to, "admin"))

        conn.commit()
        conn.close()

        send_task_assignment_email(assigned_to, title, description, end_date)

        flash("Task created successfully!")
        return redirect("/admin-dashboard")

    conn.close()
    return render_template("create_task.html", employees=employees)

# =========================
# USER DASHBOARD
# =========================
@app.route("/user-dashboard")
def user_dashboard():
    if "user_email" not in session:
        return redirect("/")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, title, description, end_date, status FROM tasks WHERE assigned_to=%s",
        (session["user_email"],)
    )
    tasks = cursor.fetchall()
    conn.close()

    return render_template("user_dashboard.html", tasks=tasks)

# =========================
# ADMIN DASHBOARD
# =========================
@app.route("/admin-dashboard")
def admin_dashboard():
    if session.get("user_role") != "admin":
        return redirect("/")
    return render_template("admin_dashboard.html")

# =========================
# LOGOUT
# =========================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# =========================
# HEALTH
# =========================
@app.route("/health")
def health():
    return "OK"

if __name__ == "__main__":
    app.run(debug=True)
