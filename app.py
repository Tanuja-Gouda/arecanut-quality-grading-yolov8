from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import os
import matplotlib.pyplot as plt

from datetime import datetime
from ultralytics import YOLO
import cv2

app = Flask(__name__)
app.secret_key = "supersecretkey"

UPLOAD_FOLDER = os.path.join("static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
DATABASE = "scan_history.db"

# Initialize database
def init_db():
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        # Users table
        c.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL)''')
        # Scans table
        c.execute('''CREATE TABLE IF NOT EXISTS scans (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        filename TEXT,
                        result TEXT,
                        timestamp TEXT,
                        user_id INTEGER)''')  # new column user_id
        conn.commit()

# Ensure existing database has user_id column
def add_user_id_column():
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute("PRAGMA table_info(scans)")
        columns = [col[1] for col in c.fetchall()]
        if "user_id" not in columns:
            c.execute("ALTER TABLE scans ADD COLUMN user_id INTEGER")
            conn.commit()

# Flask-Login setup
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

class User(UserMixin):
    def __init__(self, id_, username, password):
        self.id = id_
        self.username = username
        self.password = password

@login_manager.user_loader
def load_user(user_id):
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE id=?", (user_id,))
        row = c.fetchone()
        if row:
            return User(id_=row[0], username=row[1], password=row[2])
    return None

# Routes
@app.route("/")
def root():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    return redirect(url_for("login"))

@app.route("/index")
@login_required
def index():
    return render_template("index.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        hashed_pw = generate_password_hash(password, method="pbkdf2:sha256")
        try:
            with sqlite3.connect(DATABASE) as conn:
                c = conn.cursor()
                c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_pw))
                conn.commit()
            flash("Signup successful! Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Username already exists.", "danger")
    return render_template("signup.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        with sqlite3.connect(DATABASE) as conn:
            c = conn.cursor()
            c.execute("SELECT * FROM users WHERE username=?", (username,))
            row = c.fetchone()
            if row and check_password_hash(row[2], password):
                user = User(id_=row[0], username=row[1], password=row[2])
                login_user(user)
                return redirect(url_for("index"))
            else:
                flash("Invalid username or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# ---- Dashboard and Prediction ----
@app.route("/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    if request.method == "POST":
        file = request.files["file"]
        if file:
            filename = file.filename
            allowed_extensions = {"png", "jpg", "jpeg", "gif"}

            # ✅ Check if file extension is allowed
            if "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_extensions:
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)
            else:
                flash("Only image files (.png, .jpg, .jpeg, .gif) are allowed.", "danger")
                return redirect(url_for("dashboard"))

            # ✅ YOLO prediction
            model = YOLO("weights/best.pt")  # your trained model
            results = model.predict(source=filepath, save=False)

            # ✅ Annotate image manually
            annotated_img = results[0].plot()
            annotated_path = os.path.join(UPLOAD_FOLDER, "annotated_" + filename)
            cv2.imwrite(annotated_path, annotated_img[..., ::-1])  # RGB → BGR

            # ✅ Count objects
            boxes = results[0].boxes
            grades = []
            if len(boxes):
                for cls in boxes.cls:
                    grades.append("Grade A" if int(cls) == 0 else "Grade B")
            grade_a = grades.count("Grade A")
            grade_b = grades.count("Grade B")
            total_count = grade_a + grade_b

            # ✅ Determine final grade
            if grade_a == 0 and grade_b == 0:
                final_grade = "Invalid"
            elif grade_a >= grade_b:
                final_grade = "Grade A"
            else:
                final_grade = "Grade B"

            # ✅ Save scan to DB with user ID
            with sqlite3.connect(DATABASE) as conn:
                c = conn.cursor()
                c.execute(
                    "INSERT INTO scans (filename, result, timestamp, user_id) VALUES (?, ?, ?, ?)",
                    (filename, final_grade, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), current_user.id)
                )
                conn.commit()

            # ✅ Render result page
            return render_template(
                "result.html",
                grade_a=grade_a,
                grade_b=grade_b,
                total_count=total_count,
                final_grade=final_grade,
                image=url_for("static", filename=f"uploads/annotated_{filename}")
            )

    return render_template("dashboard.html")


# History (per-user)
# @app.route("/history")
# @login_required
# def history():
#     with sqlite3.connect(DATABASE) as conn:
#         c = conn.cursor()
#         c.execute(
#             "SELECT filename, result, timestamp FROM scans WHERE user_id=? ORDER BY id DESC",
#             (current_user.id,)
#         )
#         scans = c.fetchall()
#     return render_template("history.html", scans=scans)


@app.route("/history", endpoint="history")
@login_required
def history():
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT filename, result, timestamp FROM scans WHERE user_id=? ORDER BY id DESC",
            (current_user.id,)
        )
        scans = c.fetchall()
    return render_template("history.html", scans=scans)


@app.route("/history_graph")
@login_required
def history_graph():
    # Fetch user history data
    with sqlite3.connect(DATABASE) as conn:
        c = conn.cursor()
        c.execute(
            "SELECT result FROM scans WHERE user_id=? ORDER BY id DESC",
            (current_user.id,)
        )
        results = [r[0] for r in c.fetchall()]

    if not results:
        flash("No history data available to plot.", "info")
        return redirect(url_for("history"))

    # Count grades
    grade_a = results.count("Grade A")
    grade_b = results.count("Grade B")

    # Plot and save image
    plt.figure(figsize=(6, 4))
    plt.bar(["Grade A", "Grade B"], [grade_a, grade_b], color=["#25a517", "#555"])
    plt.title("Your Scan History")
    plt.xlabel("Grades")
    plt.ylabel("Count")

    # Save plot
    plot_path = os.path.join("static", "uploads", "history_plot.png")
    plt.tight_layout()
    plt.savefig(plot_path)
    plt.close()

    return render_template("history_graph.html")

# Run app
if __name__ == "__main__":
    init_db()
    add_user_id_column()
    app.run(debug=True)
