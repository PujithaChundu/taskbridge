from flask import Flask, render_template, request, redirect, session, send_from_directory, flash
import os
import psycopg2
import requests

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
    conn = psycopg2.connect(database_url)
    return conn

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

    conn.commit()
    conn.close()

init_db()

# =========================
# EMAIL FUNCTIONS (RESEND)
# =========================
def send_welcome_email(to_email, role):
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
        "subject": "Welcome to TaskBridge!",
        "html": f"<p>Welcome to TaskBridge! You signed up as <b>{role}</b>.</p>"
    }

    r = requests.post(url, json=data, headers=headers)
    print("Resend response:", r.text)


def send_task_assign_email(to_email, title, description, end_date):
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
        "subject": "New Task Assigned",
        "html": f"""
        <p><b>Title:</b> {title}</p>
        <p><b>Description:</b> {description}</p>
        <p><b>Deadline:</b> {end_date}</p>
        """
    }

    r = requests.post(url, json=data, headers=headers)
    print("Resend response:", r.text)

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

            send_welcome_email(email, role)
            flash("✅ Account created successfully! Please login.", "success")
            return redirect("/")
        except Exception as e:
            print(e)
            flash("❌ This email is already registered.", "error")
            return redirect("/signup")

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
# UPDATE TASK STATUS (USER)
# =========================
@app.route("/update-task-status", methods=["POST"])
def update_task_status():
    if "user_email" not in session:
        flash("❌ Please login again.", "error")
        return redirect("/")

    task_id = request.form["task_id"]
    new_status = request.form["status"]

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET status=%s WHERE id=%s", (new_status, task_id))
    conn.commit()
    conn.close()

    flash("✅ Task status updated!", "success")
    return redirect("/user-dashboard")

# =========================
# CREATE TASK (ADMIN)
# =========================
@app.route("/create-task", methods=["GET", "POST"])
def create_task():
    if "user_role" not in session or session["user_role"] != "admin":
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

        file = request.files.get("attachment")
        filename = None
        if file and file.filename:
            filename = file.filename
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        cursor.execute("""
            INSERT INTO tasks (title, description, end_date, status, assigned_to, created_by, attachment)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (title, description, end_date, "Pending", assigned_to, "admin", filename))

        conn.commit()
        conn.close()

        send_task_assign_email(assigned_to, title, description, end_date)
        flash("✅ Task created successfully!", "success")
        return redirect("/admin-dashboard")

    conn.close()
    return render_template("create_task.html", employees=employees)

# =========================
# ADMIN - VIEW ALL TASKS
# =========================
@app.route("/admin-tasks")
def admin_tasks():
    if "user_role" not in session or session["user_role"] != "admin":
        return redirect("/")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, description, end_date, status, assigned_to, attachment FROM tasks")
    tasks = cursor.fetchall()
    conn.close()

    return render_template("admin_tasks.html", tasks=tasks)

# =========================
# DELETE TASK
# =========================
@app.route("/delete-task/<int:task_id>")
def delete_task(task_id):
    if "user_role" not in session or session["user_role"] != "admin":
        return redirect("/")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id=%s", (task_id,))
    conn.commit()
    conn.close()

    flash("🗑️ Task deleted successfully!", "success")
    return redirect("/admin-tasks")

# =========================
# EDIT TASK
# =========================
@app.route("/edit-task/<int:task_id>", methods=["GET", "POST"])
def edit_task(task_id):
    if "user_role" not in session or session["user_role"] != "admin":
        return redirect("/")

    conn = get_db_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        title = request.form["title"]
        description = request.form["description"]
        end_date = request.form["end_date"]
        status = request.form["status"]
        assigned_to = request.form["assigned_to"]

        cursor.execute("SELECT attachment FROM tasks WHERE id=%s", (task_id,))
        old_file = cursor.fetchone()[0]

        file = request.files.get("attachment")
        filename = old_file
        if file and file.filename:
            filename = file.filename
            file.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))

        cursor.execute("""
            UPDATE tasks
            SET title=%s, description=%s, end_date=%s, status=%s, assigned_to=%s, attachment=%s
            WHERE id=%s
        """, (title, description, end_date, status, assigned_to, filename, task_id))

        conn.commit()
        conn.close()

        flash("✏️ Task updated successfully!", "success")
        return redirect("/admin-tasks")

    cursor.execute("SELECT title, description, end_date, status, assigned_to, attachment FROM tasks WHERE id=%s", (task_id,))
    task = cursor.fetchone()

    cursor.execute("SELECT email FROM users WHERE role='user'")
    employees = cursor.fetchall()

    conn.close()
    return render_template("edit_task.html", task=task, task_id=task_id, employees=employees)

# =========================
# FILE SERVING
# =========================
@app.route("/uploads/<filename>")
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

# =========================
# RUN
# =========================
@app.route("/health")
def health():
    return "OK"
if __name__ == "__main__":
    app.run(debug=True)

