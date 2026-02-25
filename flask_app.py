from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory
import os
import time
import sqlite3
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

app = Flask(__name__)
app.secret_key = "change-this-secret-key"

BASE_DIR = '/home/Devsobhan12221/mysite'
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
DB_PATH = os.path.join(BASE_DIR, 'users.db')
TXT_PATH = os.path.join(BASE_DIR, 'users.txt')
PDF_PATH = os.path.join(BASE_DIR, 'users.pdf')

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            ip TEXT,
            register_date TEXT,
            last_login TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            visits INTEGER
        )
    """)
    cur.execute("SELECT * FROM stats")
    if cur.fetchone() is None:
        cur.execute("INSERT INTO stats (visits) VALUES (0)")
    conn.commit()
    conn.close()

init_db()

def get_file_info(filename):
    path = os.path.join(UPLOAD_FOLDER, filename)
    size = os.path.getsize(path) / 1024
    date = time.strftime('%Y-%m-%d %H:%M', time.localtime(os.path.getmtime(path)))
    ext = os.path.splitext(filename)[1].lower()
    if ext in ['.jpg', '.jpeg', '.png', '.gif']:
        category = 'عکس'
    elif ext in ['.pdf']:
        category = 'PDF'
    elif ext in ['.mp4', '.mov', '.avi', '.mkv']:
        category = 'ویدیو'
    else:
        category = 'سایر'
    return {"name": filename, "size": f"{size:.1f} KB", "date": date, "category": category}

def generate_users_pdf():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, username, password, ip, register_date, last_login FROM users")
    users = cur.fetchall()
    conn.close()
    c = canvas.Canvas(PDF_PATH, pagesize=A4)
    width, height = A4
    y = height - 40
    c.setFont("Helvetica", 10)
    for u in users:
        line = f"ID: {u[0]} | Username: {u[1]} | Password: {u[2]} | IP: {u[3]} | Register: {u[4]} | Last Login: {u[5] or '—'}"
        if y < 40:
            c.showPage()
            c.setFont("Helvetica", 10)
            y = height - 40
        c.drawString(40, y, line)
        y -= 14
    c.save()

def sync_txt_to_db():
    if not os.path.exists(TXT_PATH):
        return
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM users")
    with open(TXT_PATH, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("|")
            if len(parts) >= 4:
                username = parts[0].strip()
                password = parts[1].strip()
                ip = parts[2].strip()
                register_date = parts[3].strip()
                cur.execute(
                    "INSERT INTO users (username, password, ip, register_date) VALUES (?, ?, ?, ?)",
                    (username, password, ip, register_date)
                )
    conn.commit()
    conn.close()
    generate_users_pdf()

@app.route("/sync-txt")
def sync_txt_route():
    sync_txt_to_db()
    return "✅ همگام‌سازی TXT با DB و PDF انجام شد"

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        if not username or not password:
            return "❌ لطفاً نام کاربری و رمز را وارد کنید"
        user_ip = request.remote_addr
        register_date = time.strftime('%Y-%m-%d %H:%M')
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute(
                "INSERT INTO users (username, password, ip, register_date) VALUES (?, ?, ?, ?)",
                (username, password, user_ip, register_date)
            )
            conn.commit()
            conn.close()
            with open(TXT_PATH, "a", encoding="utf-8") as f:
                f.write(f"{username} | {password} | {user_ip} | {register_date}\n")
            sync_txt_to_db()
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            return "❌ این نام کاربری قبلاً ثبت شده"
        except Exception as e:
            return f"❌ خطا: {e}"
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"].strip()
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT password FROM users WHERE username=?", (username,))
        user = cur.fetchone()
        conn.close()
        if user and user[0] == password:
            session["user"] = username
            user_ip = request.remote_addr
            last_login = time.strftime('%Y-%m-%d %H:%M')
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("UPDATE users SET last_login=?, ip=? WHERE username=?",
                        (last_login, user_ip, username))
            conn.commit()
            conn.close()
            generate_users_pdf()
            return redirect(url_for("index"))
        else:
            return "❌ نام کاربری یا رمز عبور اشتباه است"
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    return redirect(url_for("login"))

@app.route("/")
def index():
    if "user" not in session:
        return redirect(url_for("login"))
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("UPDATE stats SET visits = visits + 1 WHERE id=1")
    conn.commit()
    cur.execute("SELECT visits FROM stats WHERE id=1")
    total_visits = cur.fetchone()[0]
    conn.close()
    search = request.args.get("search", "").lower()
    sort = request.args.get("sort")
    category_filter = request.args.get("category", "همه")
    files = []
    for f in os.listdir(UPLOAD_FOLDER):
        info = get_file_info(f)
        if search and search not in info["name"].lower():
            continue
        if category_filter != "همه" and info["category"] != category_filter:
            continue
        files.append(info)
    if sort == "new":
        files.sort(key=lambda x: x["date"], reverse=True)
    elif sort == "old":
        files.sort(key=lambda x: x["date"])
    return render_template("index.html", files=files, search=search,
                           category_filter=category_filter, total_visits=total_visits)

@app.route("/uploads/<filename>")
def download_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route("/users")
def users():
    if "user" not in session:
        return redirect(url_for("login"))
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT id, username, password, ip, register_date, last_login FROM users")
    users_data = cur.fetchall()
    cur.execute("SELECT visits FROM stats WHERE id=1")
    total_visits = cur.fetchone()[0]
    conn.close()
    return render_template("users.html", users=users_data, total_visits=total_visits)

@app.route("/download-users")
def download_users_pdf():
    generate_users_pdf()
    return send_from_directory(os.path.dirname(PDF_PATH),
                               os.path.basename(PDF_PATH),
                               as_attachment=True)

@app.route("/change-password", methods=["GET", "POST"])
def change_password():
    if "user" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        old_password = request.form["old_password"].strip()
        new_password = request.form["new_password"].strip()
        confirm_password = request.form.get("confirm_password", "").strip()

        if not old_password or not new_password:
            return "❌ لطفاً رمز فعلی و رمز جدید را وارد کنید"
        if new_password != confirm_password:
            return "❌ رمز جدید و تکرار آن یکسان نیست"

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT password FROM users WHERE username=?", (session["user"],))
        user = cur.fetchone()

        if user and user[0] == old_password:
            cur.execute("UPDATE users SET password=? WHERE username=?", (new_password, session["user"]))
            conn.commit()
            conn.close()

            if os.path.exists(TXT_PATH):
                lines = []
                with open(TXT_PATH, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith(session["user"] + " |"):
                            parts = line.strip().split("|")
                            parts[1] = new_password
                            lines.append(" | ".join(parts) + "\n")
                        else:
                            lines.append(line)
                with open(TXT_PATH, "w", encoding="utf-8") as f:
                    f.writelines(lines)

            sync_txt_to_db()

            return "✅ رمز عبور با موفقیت تغییر کرد"
        else:
            conn.close()
            return "❌ رمز فعلی اشتباه است"

    return render_template("change_password.html")

if __name__ == "__main__":
    app.run(debug=True)
