import json
import os
from functools import wraps
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_from_directory
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()
app.template_folder = "templates"
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
AVATAR_FOLDER = os.path.join(UPLOAD_FOLDER, "avatars")
QUEST_PROOF_FOLDER = os.path.join(UPLOAD_FOLDER, "quest_proofs")
CV_PROOF_FOLDER = os.path.join(UPLOAD_FOLDER, "cv_proofs")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(AVATAR_FOLDER, exist_ok=True)
os.makedirs(QUEST_PROOF_FOLDER, exist_ok=True)
os.makedirs(CV_PROOF_FOLDER, exist_ok=True)

from ai_extractor import extract_cv, process_text_entry, validate_cv_proof, CLASS_MAP
from game_mechanics import (
    are_friends, get_friends, count_friends,
    get_friend_requests_incoming, get_friend_requests_outgoing,
    send_friend_request, accept_friend_request, reject_friend_request, remove_friend,
    generate_quests, complete_quest,
)

@app.template_filter("from_json")
def from_json(value):
    if not value:
        return []
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return []

from db import get_db, init_db
from auth import login_required, employer_required, login_user, register_user

init_db()

# ── University role decorator ──

def university_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("role") != "University":
            flash("University access only", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated

# ── Context processor ──

@app.context_processor
def inject_unread():
    if "user_id" in session and session.get("role") == "candidate":
        conn = get_db()
        count = conn.execute(
            "SELECT COUNT(*) FROM notifications WHERE user_id = ? AND read = 0",
            (session["user_id"],),
        ).fetchone()[0]
        conn.close()
        return {"unread_notifications": count}
    return {"unread_notifications": 0}

# ── Index ──

@app.route("/")
def index():
    if "user_id" in session:
        role = session.get("role")
        if role == "employer":
            return redirect(url_for("employer_dashboard"))
        if role == "University":
            return redirect(url_for("university_dashboard"))
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

# ── Auth ──

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if login_user(request.form["username"], request.form["password"]):
            role = session.get("role")
            if role == "employer":
                return redirect(url_for("employer_dashboard"))
            if role == "University":
                return redirect(url_for("university_dashboard"))
            return redirect(url_for("dashboard"))
        flash("Invalid credentials", "danger")
    return render_template("login.html")

@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        role = request.form.get("role", "candidate")
        avatar = request.form.get("avatar", "").strip()
        success, msg = register_user(
            request.form["username"],
            request.form["email"],
            request.form["password"],
            avatar=avatar,
            role=role,
            company_name=request.form.get("company_name", ""),
            industry=request.form.get("industry", ""),
            website=request.form.get("website", ""),
            contact_email=request.form.get("contact_email", ""),
            university_name=request.form.get("university_name", ""),
            university_type=request.form.get("university_type", ""),
            university_website=request.form.get("university_website", ""),
            university_email=request.form.get("university_email", ""),
        )
        if success:
            login_user(request.form["username"], request.form["password"])
            if role == "employer":
                flash("Company registered! Welcome to CareerOS.", "success")
                return redirect(url_for("employer_dashboard"))
            if role == "University":
                flash("University registered! Welcome to CareerOS.", "success")
                return redirect(url_for("university_dashboard"))
            flash("Welcome to CareerOS!", "success")
            return redirect(url_for("dashboard"))
        flash(msg, "danger")
    return render_template("signup.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out", "info")
    return redirect(url_for("login"))

# ── Candidate dashboard ──

@app.route("/dashboard")
@login_required
def dashboard():
    uid = session["user_id"]
    conn = get_db()
    profile = conn.execute(
        "SELECT * FROM player_profiles WHERE user_id = ?", (uid,)
    ).fetchone()
    active_events = conn.execute(
        "SELECT * FROM events WHERE active = 1 AND (end_time IS NULL OR end_time > datetime('now'))"
    ).fetchall()
    incoming = get_friend_requests_incoming(conn, uid)
    friend_count = count_friends(conn, uid)
    quests = json.loads(profile["quests"]) if profile and profile["quests"] else []
    avatar = profile["avatar"] if profile and profile["avatar"] else "🧑"
    conn.close()
    return render_template(
        "dashboard.html",
        profile=profile,
        username=session["username"],
        events=active_events,
        avatar=avatar,
        incoming_requests=incoming[:3],
        friend_count=friend_count,
        quests=quests,
    )

# ── Candidate profile ──

@app.route("/profile/<username>")
@login_required
def profile(username):
    uid = session["user_id"]
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not user:
        conn.close()
        flash("Player not found", "danger")
        return redirect(url_for("dashboard"))
    profile = conn.execute(
        "SELECT * FROM player_profiles WHERE user_id = ?", (user["id"],)
    ).fetchone()
    is_friend = are_friends(conn, uid, user["id"])
    p_friend_count = count_friends(conn, user["id"])
    quests = json.loads(profile["quests"]) if profile and profile["quests"] else []
    completed = sum(1 for q in quests if q.get("status") == "completed")
    p_avatar = profile["avatar"] if profile and profile["avatar"] else "🧑"
    is_own = uid == user["id"]
    is_employer_view = session.get("role") == "employer"
    conn.close()
    return render_template(
        "profile.html",
        profile=profile,
        p_username=username,
        p_user_id=user["id"],
        is_friend=is_friend,
        p_friend_count=p_friend_count,
        p_avatar=p_avatar,
        is_own=is_own,
        is_employer_view=is_employer_view,
        quests_completed=completed,
    )

@app.route("/profile/update-contact", methods=["POST"])
@login_required
def update_contact():
    uid = session["user_id"]
    name = request.form.get("name", "")
    email = request.form.get("email", "")
    phone = request.form.get("phone", "")
    location = request.form.get("location", "")
    social_media_text = request.form.get("social_media", "")
    social_media = [s.strip() for s in social_media_text.split('\n') if s.strip()]
    conn = get_db()
    profile = conn.execute(
        "SELECT cv_data FROM player_profiles WHERE user_id = ?", (uid,)
    ).fetchone()
    cv_data = {}
    if profile and profile["cv_data"]:
        try:
            cv_data = json.loads(profile["cv_data"])
        except Exception:
            cv_data = {}
    if "meta" not in cv_data:
        cv_data["meta"] = {}
    cv_data["meta"]["name"] = name
    cv_data["meta"]["email"] = email
    cv_data["meta"]["phone"] = phone
    cv_data["meta"]["location"] = location
    cv_data["meta"]["social_media"] = social_media
    conn.execute(
        "UPDATE player_profiles SET cv_data = ? WHERE user_id = ?",
        (json.dumps(cv_data), uid)
    )
    conn.commit()
    conn.close()
    flash("Contact information updated successfully!", "success")
    return redirect(url_for("profile", username=session["username"]))

# ── Friends ──

@app.route("/friends")
@login_required
def friends_page():
    uid = session["user_id"]
    conn = get_db()
    friends_list = get_friends(conn, uid)
    incoming = get_friend_requests_incoming(conn, uid)
    outgoing = get_friend_requests_outgoing(conn, uid)
    conn.close()
    return render_template(
        "friends.html",
        friends=friends_list,
        incoming_requests=incoming,
        outgoing_requests=outgoing,
    )

# ── Avatar ──

ALLOWED_AVATAR_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

@app.route("/profile/update-avatar", methods=["POST"])
@login_required
def update_avatar():
    uid = session["user_id"]
    conn = get_db()
    if "avatar_file" in request.files:
        f = request.files["avatar_file"]
        if f.filename:
            ext = os.path.splitext(f.filename)[1].lower()
            if ext in ALLOWED_AVATAR_EXT:
                filename = f"{uid}{ext}"
                f.save(os.path.join(AVATAR_FOLDER, filename))
                conn.execute(
                    "UPDATE player_profiles SET avatar = ? WHERE user_id = ?",
                    (f"custom:{filename}", uid)
                )
                conn.commit()
                conn.close()
                flash("Avatar updated!", "success")
                return redirect(url_for("profile", username=session["username"]))
    emoji = request.form.get("avatar", "").strip()
    if emoji:
        conn.execute(
            "UPDATE player_profiles SET avatar = ? WHERE user_id = ?", (emoji, uid)
        )
        conn.commit()
        conn.close()
        flash("Avatar updated!", "success")
        return redirect(url_for("profile", username=session["username"]))
    conn.close()
    flash("No avatar provided", "danger")
    return redirect(url_for("profile", username=session["username"]))

# ── Friend action routes ──

@app.route("/friend/send/<int:user_id>", methods=["POST"])
@login_required
def friend_send(user_id):
    uid = session["user_id"]
    conn = get_db()
    success, msg = send_friend_request(conn, uid, user_id)
    conn.close()
    return jsonify({"success": success, "message": msg})

@app.route("/friend/accept/<int:request_id>", methods=["POST"])
@login_required
def friend_accept(request_id):
    uid = session["user_id"]
    conn = get_db()
    success, msg = accept_friend_request(conn, request_id, uid)
    conn.close()
    flash(msg, "success" if success else "danger")
    return redirect(url_for("friends_page"))

@app.route("/friend/reject/<int:request_id>", methods=["POST"])
@login_required
def friend_reject(request_id):
    uid = session["user_id"]
    conn = get_db()
    success, msg = reject_friend_request(conn, request_id, uid)
    conn.close()
    flash(msg, "info" if success else "danger")
    return redirect(url_for("friends_page"))

@app.route("/friend/remove/<int:friend_id>", methods=["POST"])
@login_required
def friend_remove(friend_id):
    uid = session["user_id"]
    conn = get_db()
    success, msg = remove_friend(conn, uid, friend_id)
    conn.close()
    flash(msg, "info" if success else "danger")
    return redirect(url_for("friends_page"))

# ── CV upload ──

@app.route("/cv/upload", methods=["POST"])
@login_required
def cv_upload():
    if "cv_file" not in request.files:
        return jsonify({"error": "No file provided"}), 400
    file = request.files["cv_file"]
    if file.filename == "":
        return jsonify({"error": "Empty filename"}), 400
    if not file.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files accepted"}), 400
    filename = secure_filename(f"{session['user_id']}_{file.filename}")
    path = os.path.join(UPLOAD_FOLDER, filename)
    file.save(path)
    try:
        data = extract_cv(path)
    except Exception as e:
        return jsonify({"error": f"Extraction failed: {str(e)}"}), 500
    skills = data.get("skills", [])
    rpg_class = data.get("rpg_class", "Warrior")
    role = data.get("role", "Job title") 
    exp = data.get("experience_level", "mid")
    char_class_info = CLASS_MAP.get(rpg_class, {"icon": "?", "desc": ""})
    uid = session["user_id"]
    conn = get_db()
    profile = conn.execute(
        "SELECT * FROM player_profiles WHERE user_id = ?", (uid,)
    ).fetchone()
    existing_skills = json.loads(profile["skills"]) if profile and profile["skills"] else []
    merged = list(dict.fromkeys(existing_skills + skills))
    conn.commit()
    conn.close()
    return jsonify({
        "skills": merged,
        "rpg_class": rpg_class,
        "class_icon": char_class_info["icon"],
        "class_desc": char_class_info["desc"],
        "role": role,
        "experience": exp,
    })

# ── AI text import ──

@app.route("/cv/add-entry", methods=["POST"])
@login_required
def cv_add_entry():
    text = request.form.get("text", "").strip()
    proof = request.form.get("proof", "").strip()
    if not text:
        return jsonify({"error": "No text provided"}), 400
    if not proof:
        return jsonify({"error": "Proof of work required"}), 400
    validation = validate_cv_proof(text, proof)
    if validation and not validation.get("pass"):
        return jsonify({"error": f"Proof rejected: {validation.get('reason', 'Insufficient evidence')}"}), 400
    proof_file = ""
    if "proof_file" in request.files:
        f = request.files["proof_file"]
        if f.filename:
            ext = os.path.splitext(f.filename)[1].lower()
            if ext in {".pdf", ".png", ".jpg", ".jpeg"}:
                filename = f"{session['user_id']}_cv_{secure_filename(f.filename)}"
                f.save(os.path.join(CV_PROOF_FOLDER, filename))
                proof_file = filename
    try:
        result = process_text_entry(text)
    except Exception as e:
        return jsonify({"error": f"Processing failed: {str(e)}"}), 500
    section_type = result.get("section_type", "projects")
    entry = result.get("entry", {})
    if proof_file:
        entry["proof_file"] = proof_file
    entry["proof"] = proof
    new_skills = result.get("skills_extracted", [])
    uid = session["user_id"]
    conn = get_db()
    profile = conn.execute(
        "SELECT * FROM player_profiles WHERE user_id = ?", (uid,)
    ).fetchone()
    if not profile:
        conn.close()
        return jsonify({"error": "Profile not found"}), 404
    cv_data = json.loads(profile["cv_data"]) if profile["cv_data"] else {}
    if section_type not in cv_data:
        cv_data[section_type] = []
    cv_data[section_type].append(entry)
    existing_skills = json.loads(profile["skills"]) if profile["skills"] else []
    merged = list(dict.fromkeys(existing_skills + new_skills))
    quests = generate_quests(conn, uid)
    conn.execute(
        """UPDATE player_profiles SET
            cv_data = ?, skills = ?, quests = ?, last_login = datetime('now')
        WHERE user_id = ?""",
        (json.dumps(cv_data), json.dumps(merged), json.dumps(quests), uid),
    )
    conn.commit()
    conn.close()
    return jsonify({
        "success": True,
        "section_type": section_type,
        "entry": entry,
        "skills": new_skills,
        "merged_skills": merged,
    })

# ── Quest completion ──

@app.route("/quest/complete/<quest_id>", methods=["POST"])
@login_required
def quest_complete(quest_id):
    uid = session["user_id"]
    proof = request.form.get("proof", "").strip()
    proof_url = request.form.get("proof_url", "").strip()
    if not proof:
        return jsonify({"success": False, "error": "Proof of work is required"}), 400
    proof_file = ""
    if "proof_file" in request.files:
        f = request.files["proof_file"]
        if f.filename:
            ext = os.path.splitext(f.filename)[1].lower()
            if ext in {".pdf", ".png", ".jpg", ".jpeg"}:
                filename = f"{uid}_{quest_id}_{secure_filename(f.filename)}"
                f.save(os.path.join(QUEST_PROOF_FOLDER, filename))
                proof_file = filename
    conn = get_db()
    success, msg, xp_gain = complete_quest(conn, uid, quest_id, proof, proof_url, proof_file)
    if success:
        hi = 'hi'
    else:
        conn.close()
        return jsonify({"success": False, "error": msg}), 400
    conn.close()
    return jsonify({
        "success": True,
        "message": msg,})

# ── Quest refresh ──

@app.route("/quest/refresh", methods=["POST"])
@login_required
def quest_refresh():
    uid = session["user_id"]
    conn = get_db()
    quests = generate_quests(conn, uid)
    active_count = sum(1 for q in quests if q.get("status") == "active")
    conn.execute(
        "UPDATE player_profiles SET quests = ? WHERE user_id = ?",
        (json.dumps(quests), uid),
    )
    conn.commit()
    conn.close()
    flash(f"🔄 {active_count} new quests available!", "success")
    return redirect(url_for("dashboard"))

# ── Quest history ──

@app.route("/quest/history")
@login_required
def quest_history():
    uid = session["user_id"]
    conn = get_db()
    profile = conn.execute(
        "SELECT quests FROM player_profiles WHERE user_id = ?", (uid,)
    ).fetchone()
    conn.close()
    all_quests = json.loads(profile["quests"]) if profile and profile["quests"] else []
    completed = [q for q in all_quests if q.get("status") == "completed"]
    active = [q for q in all_quests if q.get("status") == "active"]
    completed.sort(key=lambda q: q.get("completed_at", ""), reverse=True)
    return render_template(
        "quest_history.html",
        completed=completed,
        active=active,
        username=session["username"],
    )

# ── Serve uploaded files ──

@app.route("/uploads/<path:filename>")
def serve_upload(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route('/uploads/avatars/<filename>')
def serve_avatar(filename):
    return send_from_directory(AVATAR_FOLDER, filename)

# ── Employer helpers ──

def _get_employer(uid):
    conn = get_db()
    emp = conn.execute("SELECT * FROM employers WHERE user_id = ?", (uid,)).fetchone()
    conn.close()
    return dict(emp) if emp else None

def _relevant_candidates(conn, employer_id):
    candidates = conn.execute(
        """SELECT u.id, u.username, p.level, p.char_class, p.skills, p.avatar
        FROM users u JOIN player_profiles p ON u.id = p.user_id
        WHERE u.role = 'candidate'"""
    ).fetchall()
    swiped = set(
        row["candidate_id"] for row in conn.execute(
            "SELECT candidate_id FROM employer_swipes WHERE employer_id = ?", (employer_id,)
        ).fetchall()
    )
    result = []
    for c in candidates:
        if c["id"] in swiped:
            continue
        cand_skills = set()
        if c["skills"] and c["skills"].strip():
            try:
                cand_skills = set(json.loads(c["skills"]))
            except json.JSONDecodeError:
                cand_skills = set()
        if not cand_skills:
            continue
        jobs = conn.execute(
            "SELECT skills_required FROM job_listings WHERE employer_id = ? AND status = 'open'",
            (employer_id,),
        ).fetchall()
        for j in jobs:
            req = set()
            if j["skills_required"] and j["skills_required"].strip():
                try:
                    req = set(json.loads(j["skills_required"]))
                except json.JSONDecodeError:
                    req = set()
            if req and cand_skills & req:
                match_pct = int(len(cand_skills & req) / len(req) * 100) if req else 0
                result.append(dict(c) | {"match_pct": match_pct})
                break
    return result

# ── Employer routes ──

@app.route("/employer")
@login_required
@employer_required
def employer_dashboard():
    uid = session["user_id"]
    emp = _get_employer(uid)
    conn = get_db()
    jobs = conn.execute(
        "SELECT * FROM job_listings WHERE employer_id = ? ORDER BY created_at DESC",
        (emp["id"],),
    ).fetchall()
    candidates = _relevant_candidates(conn, emp["id"])
    conn.close()
    return render_template(
        "employer_dashboard.html",
        employer=emp,
        jobs=[dict(j) for j in jobs],
        candidates=candidates,
        username=session["username"],
    )

@app.route("/employer/job/create", methods=["POST"])
@login_required
@employer_required
def employer_job_create():
    emp = _get_employer(session["user_id"])
    conn = get_db()
    skills_input = request.form.get("skills", "[]").strip()
    if not skills_input:
        skills_input = "[]"
    try:
        json.loads(skills_input)
    except json.JSONDecodeError:
        skills_input = "[]"
    conn.execute(
        """INSERT INTO job_listings (employer_id, title, description, skills_required, location, salary_range)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (emp["id"], request.form["title"], request.form.get("description", ""),
         skills_input, request.form.get("location", ""),
         request.form.get("salary", "")),
    )
    conn.commit()
    conn.close()
    flash("Job posted!", "success")
    return redirect(url_for("employer_dashboard"))

@app.route("/employer/job/<int:job_id>/close", methods=["POST"])
@login_required
@employer_required
def employer_job_close(job_id):
    conn = get_db()
    conn.execute("UPDATE job_listings SET status = 'closed' WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()
    flash("Job closed", "info")
    return redirect(url_for("employer_dashboard"))

@app.route("/employer/job/<int:job_id>/delete", methods=["POST"])
@login_required
@employer_required
def employer_job_delete(job_id):
    conn = get_db()
    conn.execute("DELETE FROM job_listings WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()
    flash("Job deleted", "info")
    return redirect(url_for("employer_dashboard"))

@app.route("/employer/search")
@login_required
@employer_required
def employer_search():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"results": []})
    conn = get_db()
    if q.isdigit():
        rows = conn.execute(
            """SELECT u.id, u.username, p.level, p.char_class, p.skills, p.title, p.avatar
            FROM users u JOIN player_profiles p ON u.id = p.user_id
            WHERE u.role = 'candidate' AND u.id = ?""",
            (int(q),),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT u.id, u.username, p.level, p.char_class, p.skills, p.title, p.avatar
            FROM users u JOIN player_profiles p ON u.id = p.user_id
            WHERE u.role = 'candidate' AND u.username LIKE ?""",
            (f"%{q}%",),
        ).fetchall()
    conn.close()
    results = []
    for r in rows:
        d = dict(r)
        sk = json.loads(d["skills"]) if d["skills"] else []
        d["skills"] = sk[:6]
        results.append(d)
    return jsonify({"results": results})

@app.route("/employer/swipe/<int:candidate_id>/<action>", methods=["POST"])
@login_required
@employer_required
def employer_swipe(candidate_id, action):
    if action not in ("accepted", "rejected"):
        return jsonify({"error": "Invalid action"}), 400
    emp = _get_employer(session["user_id"])
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO employer_swipes (employer_id, candidate_id, action) VALUES (?, ?, ?)",
            (emp["id"], candidate_id, action),
        )
        conn.commit()
    except Exception:
        conn.close()
        return jsonify({"error": "Already swiped"}), 400
    conn.close()
    return jsonify({"success": True, "action": action})

@app.route("/employer/matches")
@login_required
@employer_required
def employer_matches():
    emp = _get_employer(session["user_id"])
    conn = get_db()
    rows = conn.execute(
        """SELECT es.candidate_id, u.username, p.level, p.char_class, p.skills, p.title, p.avatar
        FROM employer_swipes es
        JOIN users u ON es.candidate_id = u.id
        JOIN player_profiles p ON u.id = p.user_id
        WHERE es.employer_id = ? AND es.action = 'accepted'
        ORDER BY es.created_at DESC""",
        (emp["id"],),
    ).fetchall()
    jobs = conn.execute(
        "SELECT id, title FROM job_listings WHERE employer_id = ? AND status = 'open'",
        (emp["id"],),
    ).fetchall()
    conn.close()
    return render_template(
        "employer_matches.html",
        matches=[dict(r) for r in rows],
        jobs=[dict(j) for j in jobs],
        username=session["username"],
    )

@app.route("/employer/hire/<int:candidate_id>", methods=["POST"])
@login_required
@employer_required
def employer_hire(candidate_id):
    emp = _get_employer(session["user_id"])
    job_id = request.form.get("job_id")
    if not job_id:
        flash("Select a job", "danger")
        return redirect(url_for("employer_matches"))
    conn = get_db()
    conn.execute(
        "INSERT INTO hires (job_id, candidate_id, employer_id) VALUES (?, ?, ?)",
        (job_id, candidate_id, emp["id"]),
    )
    conn.execute(
        "UPDATE job_listings SET status = 'closed' WHERE id = ?", (job_id,)
    )
    conn.commit()
    job_title = conn.execute(
        "SELECT title FROM job_listings WHERE id = ?", (job_id,)
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO notifications (user_id, message) VALUES (?, ?)",
        (candidate_id, f"🏆 Hired by {emp['company_name']} for {job_title}."),
    )
    conn.commit()
    conn.close()
    flash("Candidate hired!", "success")
    return redirect(url_for("employer_matches"))

@app.route("/employer/profile", methods=["GET", "POST"])
@login_required
@employer_required
def employer_profile():
    uid = session["user_id"]
    emp = _get_employer(uid)
    if request.method == "POST":
        conn = get_db()
        conn.execute(
            """UPDATE employers SET company_name=?, industry=?, website=?, description=?, contact_email=?
            WHERE user_id=?""",
            (request.form["company_name"], request.form.get("industry", ""),
             request.form.get("website", ""), request.form.get("description", ""),
             request.form.get("contact_email", ""), uid),
        )
        conn.commit()
        conn.close()
        flash("Profile updated!", "success")
        return redirect(url_for("employer_profile"))
    return render_template("employer_profile.html", employer=emp, username=session["username"])

@app.route("/employer/history")
@login_required
@employer_required
def employer_history():
    emp = _get_employer(session["user_id"])
    conn = get_db()
    rows = conn.execute(
        """SELECT es.id as swipe_id, es.action, es.created_at,
        u.id as candidate_id, u.username, p.level, p.char_class, p.skills, p.title, p.avatar
        FROM employer_swipes es
        JOIN users u ON es.candidate_id = u.id
        JOIN player_profiles p ON u.id = p.user_id
        WHERE es.employer_id = ? ORDER BY es.created_at DESC""",
        (emp["id"],),
    ).fetchall()
    conn.close()
    return render_template(
        "employer_history.html",
        swipes=[dict(r) for r in rows],
        username=session["username"],
    )

@app.route("/employer/history/revert/<int:swipe_id>", methods=["POST"])
@login_required
@employer_required
def employer_history_revert(swipe_id):
    conn = get_db()
    conn.execute("DELETE FROM employer_swipes WHERE id = ?", (swipe_id,))
    conn.commit()
    conn.close()
    flash("Swipe reverted. Candidate will appear in match deck again.", "info")
    return redirect(url_for("employer_history"))

# ── Jobs ──

@app.route("/jobs")
@login_required
def jobs_browse():
    uid = session["user_id"]
    conn = get_db()
    profile = conn.execute(
        "SELECT skills FROM player_profiles WHERE user_id = ?", (uid,)
    ).fetchone()
    cand_skills = set(json.loads(profile["skills"]) if profile and profile["skills"] else [])
    rows = conn.execute(
        """SELECT j.*, e.company_name, e.industry, e.contact_email, e.user_id as emp_user_id
        FROM job_listings j JOIN employers e ON j.employer_id = e.id
        WHERE j.status = 'open' ORDER BY j.created_at DESC""",
    ).fetchall()
    listings = []
    for r in rows:
        j = dict(r)
        req = set(json.loads(j["skills_required"]) if j["skills_required"] else [])
        match_pct = int(len(cand_skills & req) / len(req) * 100) if req else 0
        j["match_pct"] = match_pct
        listings.append(j)
    notifs = conn.execute(
        "SELECT id, message, created_at FROM notifications WHERE user_id = ? AND read = 0 ORDER BY created_at DESC",
        (uid,),
    ).fetchall()
    hires = conn.execute(
        """SELECT h.*, j.title, e.company_name
        FROM hires h JOIN job_listings j ON h.job_id = j.id
        JOIN employers e ON h.employer_id = e.id
        WHERE h.candidate_id = ? ORDER BY h.created_at DESC""",
        (uid,),
    ).fetchall()
    conn.close()
    return render_template(
        "jobs_browse.html",
        jobs=listings,
        notifications=[dict(n) for n in notifs],
        hires=[dict(h) for h in hires],
        username=session["username"],
    )

@app.route("/jobs/notifications/read", methods=["POST"])
@login_required
def jobs_notifications_read():
    uid = session["user_id"]
    conn = get_db()
    conn.execute("UPDATE notifications SET read = 1 WHERE user_id = ?", (uid,))
    conn.commit()
    conn.close()
    return jsonify({"success": True})

@app.route("/jobs/<int:job_id>")
@login_required
def job_detail(job_id):
    conn = get_db()
    row = conn.execute(
        """SELECT j.*, e.company_name, e.industry, e.description as company_desc,
        e.website, e.contact_email, e.user_id as emp_user_id
        FROM job_listings j JOIN employers e ON j.employer_id = e.id
        WHERE j.id = ?""",
        (job_id,),
    ).fetchone()
    conn.close()
    if not row:
        flash("Job not found", "danger")
        return redirect(url_for("jobs_browse"))
    job = dict(row)
    job["skills_required"] = json.loads(job["skills_required"]) if job["skills_required"] else []
    return render_template("job_detail.html", job=job, username=session["username"])

# ── University helpers ──

def _get_university(uid):
    conn = get_db()
    uni = conn.execute(
        "SELECT * FROM universities WHERE user_id = ?", (uid,)
    ).fetchone()
    conn.close()
    return dict(uni) if uni else None

# ── University routes ──

@app.route("/university")
@login_required
@university_required
def university_dashboard():
    uid = session["user_id"]
    uni = _get_university(uid)
    if not uni:
        flash("University profile not found. Please contact support.", "danger")
        return redirect(url_for("logout"))

    conn = get_db()

    # Total students placed
    students_placed = conn.execute(
        "SELECT COUNT(*) FROM hires"
    ).fetchone()[0]

    # Employer partners (distinct employers with open jobs)
    employer_partners = conn.execute(
        "SELECT COUNT(DISTINCT employer_id) FROM job_listings WHERE status = 'open'"
    ).fetchone()[0]

    # Placement rate vs total candidates
    total_candidates = conn.execute(
        "SELECT COUNT(*) FROM users WHERE role = 'candidate'"
    ).fetchone()[0]
    placement_rate = (
        f"{int(students_placed / total_candidates * 100)}%"
        if total_candidates > 0 else "0%"
    )

    # Active industry events
    active_events = conn.execute(
        "SELECT * FROM events WHERE active = 1 AND (end_time IS NULL OR end_time > datetime('now'))"
    ).fetchall()

    conn.close()

    return render_template(
        "university_dashboard.html",
        university=uni,
        university_name=uni.get("university_name", session["username"]),
        university_type=uni.get("university_type", "University"),
        students_placed=f"{students_placed:,}",
        avg_salary="RM 4.8k",          # extend when salary data is stored per hire
        employer_partners=employer_partners,
        placement_rate=placement_rate,
        events=active_events,
        username=session["username"],
    )

@app.route("/university/profile", methods=["GET", "POST"])
@login_required
@university_required
def university_profile():
    uid = session["user_id"]
    uni = _get_university(uid)
    if request.method == "POST":
        conn = get_db()
        conn.execute(
            """UPDATE universities
            SET university_name=?, university_type=?, university_website=?, university_email=?
            WHERE user_id=?""",
            (
                request.form.get("university_name", ""),
                request.form.get("university_type", ""),
                request.form.get("university_website", ""),
                request.form.get("university_email", ""),
                uid,
            ),
        )
        conn.commit()
        conn.close()
        flash("University profile updated!", "success")
        return redirect(url_for("university_profile"))
    return render_template(
        "university_profile.html",
        university=uni,
        username=session["username"],
    )

# ── Run ──

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)