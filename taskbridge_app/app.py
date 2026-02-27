from flask import Flask, render_template, request, redirect, session, send_from_directory, flash
import os
import psycopg2
import requests
import secrets
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "taskbridge-secret-key")

# =========================
# CONFIG
# =========================
UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "TASKBRIDGE-ADMIN-2024")

# =========================
# DATABASE CONNECTION
# =========================
def get_db_connection():
    database_url = os.getenv("DATABASE_URL")
    return psycopg2.connect(database_url)

# =========================
# DATABASE INIT
# =========================
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

    # NEW TABLE FOR RESET TOKENS
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
# RESET TOKEN STORAGE
# =========================
reset_tokens = {}

# =========================
# EMAIL FUNCTION
# =========================
def send_email(to_email, subject, html_content):
    api_key = os.getenv("RESEND_API_KEY")
    if not api_key:
        print("No RESEND_API_KEY set")
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

            if user[0] == "admin":
                return redirect("/admin-dashboard")
            else:
                return redirect("/user-dashboard")
        else:
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

            send_email(
                email,
                "Welcome to TaskBridge!",
                f"<p>Welcome! You signed up as <b>{role}</b>.</p>"
            )

            flash("Account created successfully!")
            return redirect("/")
        except:
            flash("Email already registered")
            return redirect("/signup")

    return render_template("signup.html")

# =========================
# FORGOT PASSWORD
# =========================
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"]

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE email=%s", (email,))
        user = cursor.fetchone()

        if not user:
            conn.close()
            flash("Email not found")
            return redirect("/forgot-password")

        token = secrets.token_urlsafe(32)
        expires_at = datetime.utcnow() + timedelta(minutes=30)

        # Store token in DB
        cursor.execute(
            "INSERT INTO password_resets (email, token, expires_at) VALUES (%s, %s, %s)",
            (email, token, expires_at)
        )
        conn.commit()
        conn.close()

        reset_link = f"https://taskbridge-819w.onrender.com/reset-password/{token}"

        send_email(
            email,
            "Reset your TaskBridge password",
            f"<p>Click below to reset your password:</p><p><a href='{reset_link}'>{reset_link}</a></p>"
        )

        flash("Reset link sent to your email")
        return redirect("/")

    return render_template("forgot_password.html")

# =========================
# RESET PASSWORD
# =========================
@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT email, expires_at FROM password_resets WHERE token=%s",
        (token,)
    )
    record = cursor.fetchone()

    if not record:
        conn.close()
        return "Invalid reset link"

    email, expires_at = record

    if datetime.utcnow() > expires_at:
        cursor.execute("DELETE FROM password_resets WHERE token=%s", (token,))
        conn.commit()
        conn.close()
        return "Reset link expired"

    if request.method == "POST":
        new_password = request.form["password"]

        cursor.execute(
            "UPDATE users SET password=%s WHERE email=%s",
            (new_password, email)
        )

        # Delete token after use
        cursor.execute(
            "DELETE FROM password_resets WHERE token=%s",
            (token,)
        )

        conn.commit()
        conn.close()

        flash("Password updated successfully!")
        return redirect("/")

    conn.close()
    return render_template("reset_password.html")
# =========================
# DASHBOARDS
# =========================
@app.route("/admin-dashboard")
def admin_dashboard():
    if session.get("user_role") != "admin":
        return redirect("/")
    return render_template("admin_dashboard.html")

@app.route("/user-dashboard")
def user_dashboard():
    if "user_email" not in session:
        return redirect("/")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, title, description, end_date, status, attachment FROM tasks WHERE assigned_to=%s",
        (session["user_email"],)
    )
    tasks = cursor.fetchall()
    conn.close()

    return render_template("user_dashboard.html", tasks=tasks)

# =========================
# LOGOUT
# =========================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# =========================
# HEALTH CHECK
# =========================
@app.route("/health")
def health():
    return "OK"

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(debug=True)

