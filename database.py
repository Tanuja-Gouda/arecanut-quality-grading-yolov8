# database.py
import sqlite3
import datetime

DB_NAME = "scan_history.db"

# Create tables if not exists
def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS scans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT,
                    grade_a INTEGER,
                    grade_b INTEGER,
                    final_grade TEXT,
                    timestamp TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE,
                    password TEXT
                )''')
    conn.commit()
    conn.close()

# Insert a scan record
def insert_scan(filename, grade_a, grade_b, final_grade):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO scans (filename, grade_a, grade_b, final_grade, timestamp) VALUES (?, ?, ?, ?, ?)",
              (filename, grade_a, grade_b, final_grade, datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    conn.commit()
    conn.close()

# Get all scan records
def get_all_scans():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM scans ORDER BY timestamp DESC")
    rows = c.fetchall()
    conn.close()
    return rows

# User management
def insert_user(username, password_hash):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password_hash))
    conn.commit()
    conn.close()

def get_user(username):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE username=?", (username,))
    user = c.fetchone()
    conn.close()
    return user

# Initialize DB
init_db()
