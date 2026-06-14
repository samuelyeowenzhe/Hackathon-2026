import functools
import re
from hashlib import sha256
from flask import session, redirect, url_for, flash

def hash_password(password):
    return sha256(password.encode()).hexdigest()

def login_user(username, password):
    from db import get_db
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()
    if user and user["password_hash"] == hash_password(password):
        session["user_id"] = user["id"]
        session["username"] = user["username"]
        session["role"] = user["role"]
        return True
    return False

def register_user(username, email, password, avatar="", role="candidate",
                  company_name="", industry="", website="", contact_email="",
                  university_name="", university_type="", university_website="", university_email=""):
    from db import get_db
    if len(password) < 4:
        return False, "Password too short"
    if not re.match(r"^[a-zA-Z0-9_]{3,20}$", username):
        return False, "Username must be 3-20 alphanumeric characters"
    if role not in ("candidate", "employer", "University"):
        role = "candidate"
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
            (username, email, hash_password(password), role),
        )
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        if role == "candidate":
            if not avatar:
                avatar = "🧑"
            conn.execute(
                "INSERT INTO player_profiles (user_id, avatar) VALUES (?, ?)",
                (user["id"], avatar)
            )
        elif role == "employer":
            conn.execute(
                """INSERT INTO employers (user_id, company_name, industry, website, contact_email)
                VALUES (?, ?, ?, ?, ?)""",
                (user["id"], company_name[:100], industry[:50], website[:200], contact_email[:200]),
            )
        elif role == "University":
            conn.execute(
                """INSERT INTO universities (user_id, university_name, university_type, university_website, university_email)
                VALUES (?, ?, ?, ?, ?)""",
                (user["id"], university_name[:200], university_type[:100], university_website[:200], university_email[:200]),
            )
        conn.commit()
        conn.close()
        return True, "Account created"
    except Exception as e:
        conn.close()
        return False, str(e)

def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first", "danger")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def employer_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in first", "danger")
            return redirect(url_for("login"))
        if session.get("role") != "employer":
            flash("Employer access only", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated