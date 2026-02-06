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
    # Try to add attachment column if it doesn't exist
    try:
        cursor.execute("ALTER TABLE tasks ADD COLUMN attachment TEXT")
    except:
        pass
    conn.commit()
    conn.close()

init_db()

# =========================
# SEND RESET EMAIL FUNCTION
# =========================
def send_reset_email(to_email, reset_link):
    msg = MIMEText(f"""
You requested a password reset.

Click here to reset your password:
{reset_link}

If you did not request this, ignore this email.

— TaskBridge Team
""")

    msg["Subject"] = "TaskBridge Password Reset"
    msg["From"] = EMAIL_SENDER
    msg["To"] = to_email

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, to_email, msg.as_string())
        server.quit()
        print("Reset email sent!")
    except Exception as e:
        print("Email error:", e)

# =========================
# SEND WELCOME EMAIL FUNCTION
# =========================
def send_welcome_email(to_email, role):
    role_text = "Administrator (Manager)" if role == "admin" else "User (Employee)"

    msg = MIMEText(f"""
Welcome to TaskBridge! 🎉

Your account has been created successfully.

You have signed up as: {role_text}

You can now log in and start using TaskBridge.

— TaskBridge Team
""")

    msg["Subject"] = "Welcome to TaskBridge!"
    msg["From"] = EMAIL_SENDER
    msg["To"] = to_email

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, to_email, msg.as_string())
        server.quit()
        print("Welcome email sent!")
    except Exception as e:
        print("Email error:", e)

# =========================
# SEND TASK ASSIGN EMAIL FUNCTION  (STEP 1)
# =========================
def send_task_assign_email(to_email, title, description, end_date):
    msg = MIMEText(f"""
Hello,

You have been assigned a new task in TaskBridge.

Title: {title}
Description: {description}
Deadline: {end_date}

Please log in to TaskBridge to view and update the task status.

— TaskBridge Team
""")

    msg["Subject"] = "New Task Assigned - TaskBridge"
    msg["From"] = EMAIL_SENDER
    msg["To"] = to_email

    try:
        server = smtplib.SMTP_SSL("smtp.gmail.com", 465)
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, to_email, msg.as_string())
        server.quit()
        print("Task assignment email sent!")
    except Exception as e:
        print("Email error:", e)

# =========================
# LOGIN ROUTE
# =========================
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role FROM users WHERE email=? AND password=?",
            (email, password)
        )
        user = cursor.fetchone()
        conn.close()

        if user:
            role = user[0]
            session["user_email"] = email
            session["user_role"] = role

            if role == "admin":
                return redirect("/admin-dashboard")
            else:
                return redirect("/user-dashboard")
        else:
            return "❌ Invalid email or password"

    return render_template("login.html")

# =========================
# SIGNUP ROUTE
# =========================
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]
        role = request.form["role"]
        admin_key = request.form.get("admin_key")

        if role == "admin" and admin_key != ADMIN_SECRET_KEY:
            return "❌ Invalid Admin Secret Key"

        try:
            conn = sqlite3.connect("database.db")
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (email, password, role) VALUES (?, ?, ?)",
                (email, password, role)
            )
            conn.commit()
            conn.close()

            # Send welcome email
            send_welcome_email(email, role)

        except:
            return "❌ This email is already registered. Please go back and login."

        return "✅ Account Created Successfully! A welcome email has been sent. You can now login."

    return render_template("signup.html")

# =========================
# FORGOT PASSWORD ROUTE
# =========================
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"]

        reset_link = f"http://127.0.0.1:5000/reset-password/{email}"

        send_reset_email(email, reset_link)

        return "✅ Reset email sent! Check your inbox."

    return render_template("forgot_password.html")

# =========================
# RESET PASSWORD ROUTE
# =========================
@app.route("/reset-password/<email>", methods=["GET", "POST"])
def reset_password(email):
    if request.method == "POST":
        new_pass = request.form["password"]

        conn = sqlite3.connect("database.db")
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET password=? WHERE email=?",
            (new_pass, email)
        )
        conn.commit()
        conn.close()

        return "✅ Password updated! You can login now."

    return render_template("reset_password.html")

# =========================
# DASHBOARDS
# =========================
@app.route("/admin-dashboard")
def admin_dashboard():
    return render_template("admin_dashboard.html")

@app.route("/user-dashboard")
def user_dashboard():
    if "user_email" not in session:
        return redirect("/")

    user_email = session["user_email"]

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, description, end_date, status, attachment FROM tasks WHERE assigned_to=?", (user_email,))
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
# CREATE TASK (ADMIN)
# =========================
@app.route("/create-task", methods=["GET", "POST"])
def create_task():
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Get all employees
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

        if file and file.filename != "":
            filename = file.filename
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        cursor.execute("""
            INSERT INTO tasks (title, description, end_date, status, assigned_to, created_by, attachment)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (title, description, end_date, status, assigned_to, created_by, filename))

        conn.commit()
        conn.close()

        # Send email to assigned employee
        send_task_assign_email(assigned_to, title, description, end_date)
        flash("✅ Task created successfully!")
        return redirect("/admin-dashboard")
    conn.close()
    return render_template("create_task.html", employees=employees)
# =========================
# UPDATE TASK STATUS (USER)
# =========================
@app.route("/update-task-status", methods=["POST"])
def update_task_status():
    if "user_email" not in session:
        return redirect("/")

    task_id = request.form["task_id"]
    new_status = request.form["status"]

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET status=? WHERE id=?", (new_status, task_id))
    conn.commit()
    conn.close()

    return redirect("/user-dashboard")
# =========================
# Adimin TASK Veiw
# =========================
@app.route("/admin-tasks")
def admin_tasks():
    if "user_role" not in session or session["user_role"] != "admin":
        return redirect("/")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, description, end_date, status, assigned_to FROM tasks")
    tasks = cursor.fetchall()
    conn.close()

    return render_template("admin_tasks.html", tasks=tasks)
# =========================
# DELETE TASK(ADMIN)
# =========================
@app.route("/delete-task/<int:task_id>")
def delete_task(task_id):
    if "user_role" not in session or session["user_role"] != "admin":
        return redirect("/")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id=?", (task_id,))
    conn.commit()
    conn.close()

    return redirect("/admin-tasks")
# =========================
# EDIT TASK (ADMIN)
# =========================
@app.route("/edit-task/<int:task_id>", methods=["GET", "POST"])
def edit_task(task_id):
    if "user_role" not in session or session["user_role"] != "admin":
        return redirect("/")

    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        end_date = request.form["end_date"]
        status = request.form["status"]
        assigned_to = request.form["assigned_to"]

        cursor.execute("""
            UPDATE tasks
            SET title=?, description=?, end_date=?, status=?, assigned_to=?
            WHERE id=?
        """, (title, description, end_date, status, assigned_to, task_id))

        conn.commit()
        conn.close()
        return redirect("/admin-tasks")

    # GET: load existing task
    cursor.execute("SELECT title, description, end_date, status, assigned_to FROM tasks WHERE id=?", (task_id,))
    task = cursor.fetchone()

    # Get employees for dropdown
    cursor.execute("SELECT email FROM users WHERE role='user'")
    employees = cursor.fetchall()

    conn.close()

    return render_template("edit_task.html", task=task, task_id=task_id, employees=employees)
# =========================
# ADD FILE FOLDER (ADMIN)
# =========================
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)
# =========================
# RUN SERVER
# =========================
if __name__ == "__main__":
    app.run(debug=True)
