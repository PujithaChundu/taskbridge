from flask import Flask, render_template, request, redirect, session, send_from_directory, flash
import os
import sqlite3
import smtplib
from email.mime.text import MIMEText

app = Flask(__name__)
app.secret_key = "taskbridge-secret-key"

UPLOAD_FOLDER = "uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

ADMIN_SECRET_KEY = "TASKBRIDGE-ADMIN-2024"

EMAIL_SENDER = "a75711100@gmail.com"
EMAIL_PASSWORD = "ksbphgozpssqkmoe"

# =========================
# DATABASE INIT
# =========================
def init_db():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password TEXT,
            role TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            description TEXT,
            end_date TEXT,
            status TEXT,
            assigned_to TEXT,
            created_by TEXT,
            attachment TEXT
        )
    """)

    conn.commit()
    conn.close()

init_db()

# =========================
# EMAIL FUNCTIONS
# =========================
def send_reset_email(to_email, reset_link):
    msg = MIMEText(f"Reset your password here:\n{reset_link}")
    msg["Subject"] = "TaskBridge Password Reset"
    msg["From"] = EMAIL_SENDER
    msg["To"] = to_email
    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, to_email, msg.as_string())
        server.quit()
    except Exception as e:
        print("Email error:", e)

def send_welcome_email(to_email, role):
    msg = MIMEText(f"Welcome to TaskBridge! You signed up as {role}.")
    msg["Subject"] = "Welcome to TaskBridge!"
    msg["From"] = EMAIL_SENDER
    msg["To"] = to_email
    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, to_email, msg.as_string())
        server.quit()
    except Exception as e:
        print("Email error:", e)

def send_task_assign_email(to_email, title, description, end_date):
    msg = MIMEText(f"New task:\n{title}\n{description}\nDeadline: {end_date}")
    msg["Subject"] = "New Task Assigned"
    msg["From"] = EMAIL_SENDER
    msg["To"] = to_email
    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, to_email, msg.as_string())
        server.quit()
    except Exception as e:
        print("Email error:", e)

# =========================
# LOGIN
# =========================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM users WHERE email=? AND password=?", (email, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session["user_email"] = email
            session["user_role"] = user[0]
            flash("✅ Login successful!", "success")

            if user[0] == "admin":
                return redirect("/admin-dashboard")
            else:
                return redirect("/user-dashboard")
        else:
            flash("❌ Invalid email or password", "error")
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
            flash("❌ Invalid Admin Secret Key", "error")
            return redirect("/")

        try:
            conn = sqlite3.connect("database.db")
            cursor = conn.cursor()
            cursor.execute("INSERT INTO users (email, password, role) VALUES (?, ?, ?)", (email, password, role))
            conn.commit()
            conn.close()

            send_welcome_email(email, role)
            flash("✅ Account created successfully! Please login.", "success")
            return redirect("/")
        except:
            flash("❌ This email is already registered.", "error")
            return redirect("/")

    return render_template("signup.html")

# =========================
# LOGOUT
# =========================
@app.route("/logout")
def logout():
    session.clear()
    flash("✅ Logged out successfully.", "success")
    return redirect("/")

# =========================
# DASHBOARDS
# =========================
@app.route("/admin-dashboard")
def admin_dashboard():
    if "user_role" not in session or session["user_role"] != "admin":
        return redirect("/")
    return render_template("admin_dashboard.html")

@app.route("/user-dashboard")
def user_dashboard():
    if "user_email" not in session:
        return redirect("/")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, description, end_date, status, attachment FROM tasks WHERE assigned_to=?", (session["user_email"],))
    tasks = cursor.fetchall()
    conn.close()

    return render_template("user_dashboard.html", tasks=tasks)

# =========================
# CREATE TASK
# =========================
@app.route("/create-task", methods=["GET", "POST"])
def create_task():
    if "user_role" not in session or session["user_role"] != "admin":
        return redirect("/")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT email FROM users WHERE role='user'")
    employees = cursor.fetchall()

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        end_date = request.form["end_date"]
        assigned_to = request.form["assigned_to"]
        status = "Pending"
        created_by = "admin"

        file = request.files.get("attachment")
        filename = None
        if file and file.filename:
            filename = file.filename
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        cursor.execute("""
            INSERT INTO tasks (title, description, end_date, status, assigned_to, created_by, attachment)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (title, description, end_date, status, assigned_to, created_by, filename))

        conn.commit()
        conn.close()

        send_task_assign_email(assigned_to, title, description, end_date)
        flash("✅ Task created successfully!", "success")
        return redirect("/")

    conn.close()
    return render_template("create_task.html", employees=employees)

# =========================
# FILES
# =========================
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# =========================
# RUN
# =========================
if __name__ == "__main__":
    app.run(debug=True)
