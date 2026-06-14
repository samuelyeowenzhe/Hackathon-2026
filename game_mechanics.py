import json
from datetime import datetime
from ai_extractor import _call_deepseek

<<<<<<< HEAD
def xp_for_level(level):
    """XP needed to go from `level` to `level+1`."""
    return int(100 * (level ** 1.5))

def check_level_up(conn, user_id):
    """Loop: while xp >= threshold, level up (full heal each time)."""
    profile = conn.execute(
        "SELECT level, xp, xp_to_next, hp, max_hp FROM player_profiles WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if not profile:
        return {"leveled_up": False, "levels_gained": 0, "new_level": 1}

    level = profile["level"]
    xp = profile["xp"]
    hp = profile["hp"]
    max_hp = profile["max_hp"]
    threshold = profile["xp_to_next"] if level == 1 else xp_for_level(level)
    levels_gained = 0

    while xp >= threshold:
        xp -= threshold
        level += 1
        max_hp += 10
        hp = max_hp
        levels_gained += 1
        threshold = xp_for_level(level)

    conn.execute(
        """UPDATE player_profiles SET
            level = ?, xp = ?, xp_to_next = ?, hp = ?, max_hp = ?
        WHERE user_id = ?""",
        (level, xp, threshold, hp, max_hp, user_id),
    )
    conn.commit()

    return {
        "leveled_up": levels_gained > 0,
        "levels_gained": levels_gained,
        "new_level": level,
    }

=======
>>>>>>> 710af19ae02d28a48500c572b4a9ce4c5c947428
# ── Friend helpers ──

def are_friends(conn, user_a, user_b):
    if user_a == user_b:
        return False
    row = conn.execute(
        """SELECT 1 FROM friend_requests
        WHERE ((from_user = ? AND to_user = ?) OR (from_user = ? AND to_user = ?))
        AND status = 'accepted'""",
        (user_a, user_b, user_b, user_a),
    ).fetchone()
    return row is not None

def get_friends(conn, user_id):
    rows = conn.execute(
        """SELECT u.id, u.username, p.level, p.char_class, p.title, p.avatar, p.last_login
        FROM friend_requests fr
        JOIN users u ON (CASE WHEN fr.from_user = ? THEN fr.to_user ELSE fr.from_user END) = u.id
        JOIN player_profiles p ON u.id = p.user_id
        WHERE (fr.from_user = ? OR fr.to_user = ?) AND fr.status = 'accepted'""",
        (user_id, user_id, user_id),
    ).fetchall()
    return [dict(r) for r in rows]

def count_friends(conn, user_id):
    return len(get_friends(conn, user_id))

def get_friend_requests_incoming(conn, user_id):
    rows = conn.execute(
        """SELECT fr.id, fr.from_user, u.username, p.char_class, p.level, p.avatar, fr.timestamp
        FROM friend_requests fr
        JOIN users u ON fr.from_user = u.id
        JOIN player_profiles p ON u.id = p.user_id
        WHERE fr.to_user = ? AND fr.status = 'pending'
        ORDER BY fr.timestamp DESC""",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]

def get_friend_requests_outgoing(conn, user_id):
    rows = conn.execute(
        """SELECT fr.id, fr.to_user, u.username, p.char_class, p.level, p.avatar, fr.timestamp
        FROM friend_requests fr
        JOIN users u ON fr.to_user = u.id
        JOIN player_profiles p ON u.id = p.user_id
        WHERE fr.from_user = ? AND fr.status = 'pending'
        ORDER BY fr.timestamp DESC""",
        (user_id,),
    ).fetchall()
    return [dict(r) for r in rows]

def send_friend_request(conn, from_id, to_id):
    if from_id == to_id:
        return False, "Cannot friend yourself"
    if are_friends(conn, from_id, to_id):
        return False, "Already friends"
    existing = conn.execute(
        "SELECT 1 FROM friend_requests WHERE from_user = ? AND to_user = ? AND status = 'pending'",
        (from_id, to_id),
    ).fetchone()
    if existing:
        return False, "Request already sent"
    reverse = conn.execute(
        "SELECT 1 FROM friend_requests WHERE from_user = ? AND to_user = ? AND status = 'pending'",
        (to_id, from_id),
    ).fetchone()
    if reverse:
        return False, "This user already sent you a request"
    conn.execute(
        "INSERT INTO friend_requests (from_user, to_user, status) VALUES (?, ?, 'pending')",
        (from_id, to_id),
    )
    conn.commit()
    return True, "Friend request sent!"

def accept_friend_request(conn, request_id, user_id):
    row = conn.execute(
        "SELECT * FROM friend_requests WHERE id = ? AND to_user = ? AND status = 'pending'",
        (request_id, user_id),
    ).fetchone()
    if not row:
        return False, "Request not found"
    conn.execute("UPDATE friend_requests SET status = 'accepted' WHERE id = ?", (request_id,))
    conn.commit()
    return True, "Friend request accepted!"

def reject_friend_request(conn, request_id, user_id):
    row = conn.execute(
        "SELECT * FROM friend_requests WHERE id = ? AND to_user = ? AND status = 'pending'",
        (request_id, user_id),
    ).fetchone()
    if not row:
        return False, "Request not found"
    conn.execute("DELETE FROM friend_requests WHERE id = ?", (request_id,))
    conn.commit()
    return True, "Friend request rejected"

def remove_friend(conn, user_id, friend_id):
    if not are_friends(conn, user_id, friend_id):
        return False, "Not friends"
    conn.execute(
        """DELETE FROM friend_requests
        WHERE ((from_user = ? AND to_user = ?) OR (from_user = ? AND to_user = ?))
        AND status = 'accepted'""",
        (user_id, friend_id, friend_id, user_id),
    )
    conn.commit()
    return True, "Friend removed"

# ── Quest system ──


def generate_quests(conn, user_id):
    """Generate career-enhancing quests via DeepSeek. Falls back to mock when offline."""
    profile = conn.execute(
        "SELECT * FROM player_profiles WHERE user_id = ?", (user_id,)
    ).fetchone()
    if not profile:
        return []

    skills = json.loads(profile["skills"]) if profile["skills"] else []
    cv_data = json.loads(profile["cv_data"]) if profile["cv_data"] else {}
    level = profile["level"]
    old_quests = json.loads(profile["quests"]) if profile["quests"] else []
    completed = [q for q in old_quests if q.get("status") == "completed"]

    summary = {
        "level": level,
        "class": profile["char_class"],
        "title": profile["title"],
        "skills": skills,
        "work_roles": [w.get("role", "") for w in cv_data.get("work_experience", [])],
        "has_education": len(cv_data.get("education", [])) > 0,
        "has_projects": len(cv_data.get("projects", [])) > 0,
        "has_leadership": len(cv_data.get("leadership", [])) > 0,
        "friend_count": count_friends(conn, user_id),
    }

    try:
        result = _call_deepseek(
            "You are a career coach AI for LifeQuest, an RPG career development game.\n\n"
            "Generate 3-5 career-enhancing quests for this player profile. "
            "Each quest must be specific, actionable, and help advance their real career.\n\n"
            f"Player Profile:\n{json.dumps(summary, indent=2)}\n\n"
            'Output a JSON object with a "quests" array:\n'
            "{\n"
            '  "quests": [\n'
            "    {\n"
            '      "id": "q_0",\n'
            '      "category": "skill_gap|profile_completion|career_advancement|certification|social",\n'
            '      "priority": "high|medium|low",\n'
            '      "title": "Short quest title",\n'
            '      "description": "Detailed actionable description of what to do",\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Rules:\n"
<<<<<<< HEAD
            "- Each quest id must be unique (q_0, q_1, q_2, ...)\n"
            "- Categories: skill_gap (learn a missing skill), profile_completion (add CV sections), "
            "career_advancement (level up strategy), certification (earn a cert), social (network)\n"
            "- Max 5 quests\n"
            "- Make quests feel like RPG quests but grounded in real career actions",
=======
            "- Categories: skill_gap (learn a missing skill), profile_completion (add CV sections), "
            "career_advancement (level up strategy), certification (earn a cert), social (network)\n"
            "- Max 5 quests\n"
>>>>>>> 710af19ae02d28a48500c572b4a9ce4c5c947428
        )
    except Exception:
        result = None

    if result and isinstance(result, dict) and "quests" in result:
        raw = result["quests"]
    else:
        raw = _mock_quests(summary)

    sanitized = []
    for i, q in enumerate(raw[:5]):
        cat = q.get("category", "career_advancement")
        if cat not in ("skill_gap", "profile_completion", "career_advancement", "certification", "social"):
            cat = "career_advancement"
        prio = q.get("priority", "medium")
        if prio not in ("high", "medium", "low"):
            prio = "medium"
        sanitized.append({
            "id": q.get("id", f"q_{i}"),
            "category": cat,
            "priority": prio,
            "title": (q.get("title") or f"Quest {i}")[:60],
            "description": (q.get("description") or "Complete this quest to advance your career.")[:300],
<<<<<<< HEAD
            "xp_reward": max(30, min(150, int(q.get("xp_reward", 50)))),
=======
>>>>>>> 710af19ae02d28a48500c572b4a9ce4c5c947428
            "status": "active",
            "proof": "",
            "proof_url": "",
        })

    return completed + sanitized


def _mock_quests(summary):
    quests = []
    idx = 0
    skills = summary.get("skills", [])
    has_work = bool(summary.get("work_roles"))
    has_projects = summary.get("has_projects", False)
    has_edu = summary.get("has_education", False)
    has_lead = summary.get("has_leadership", False)
    friend_count = summary.get("friend_count", 0)

    if not has_work:
        quests.append(dict(id=f"q_{idx}", category="profile_completion", priority="high",
            title="Add work experience",
            description="Your profile has no work history. Add internships, freelance work, or past roles.",
            status="active", proof="", proof_url=""))
        idx += 1
    if not has_projects:
        quests.append(dict(id=f"q_{idx}", category="profile_completion", priority="medium",
            title="Build a portfolio project",
            description="Create a project using your current skills and add it to your profile.",
            status="active", proof="", proof_url=""))
        idx += 1
    if not has_edu:
        quests.append(dict(id=f"q_{idx}", category="profile_completion", priority="low",
            title="Add your education",
            description="List your degree or courses. Education builds credibility.",
            status="active", proof="", proof_url=""))
        idx += 1
    if friend_count < 3:
        quests.append(dict(id=f"q_{idx}", category="social", priority="low",
            title="Connect with more players",
            description="Networking is powerful. Connect with players to grow your professional network.",
            status="active", proof="", proof_url=""))
        idx += 1
    if idx < 5 and not has_lead:
        quests.append(dict(id=f"q_{idx}", category="career_advancement", priority="medium",
            title="Write a career reflection",
            description="Write about what you've learned recently and where you want to grow.",
            status="active", proof="", proof_url=""))
        idx += 1
    if idx < 5 and skills:
        quests.append(dict(id=f"q_{idx}", category="certification", priority="medium",
            title=f"Earn a {skills[0]} certification",
            description=f"Get certified in {skills[0]} to validate your expertise.",
            status="active", proof="", proof_url=""))

    return quests


def validate_proof(proof_text, quest_info):
    """Rate proof via DeepSeek. Returns {"score":0-10,"reason":"..."} or None."""
    if not proof_text.strip():
        return None
    try:
        result = _call_deepseek(
            "You are a proof validator for LifeQuest, an RPG career development game.\n\n"
            "Rate this proof submission from 0 to 10 based on:\n"
            "- Does it demonstrate real effort?\n"
            "- Is it credible and specific?\n"
            "- Does it meaningfully relate to the quest?\n\n"
            f"Quest: {quest_info.get('title', 'Unknown')}\n"
            f"Description: {quest_info.get('description', '')}\n"
            f"Proof: {proof_text[:2000]}\n\n"
            'Return JSON only: {"score": 0-10, "reason": "brief explanation"}'
        )
        if result and isinstance(result, dict) and isinstance(result.get("score"), (int, float)):
            result["score"] = max(0, min(10, int(result["score"])))
            return result
    except Exception:
        pass
    return None


def complete_quest(conn, user_id, quest_id, proof, proof_url="", proof_file=""):
    """Mark quest completed, validate proof, award XP (possibly halved)."""
    profile = conn.execute(
        "SELECT quests FROM player_profiles WHERE user_id = ?",
        (user_id,),
    ).fetchone()
    if not profile:
        return False, "Profile not found", 0

    quests = json.loads(profile["quests"]) if profile["quests"] else []
    found = None
    for q in quests:
        if q["id"] == quest_id and q.get("status") == "active":
            found = q
            break
    if not found:
        return False, "Quest not found or already completed", 0
    if not proof.strip():
        return False, "Proof of work required", 0

<<<<<<< HEAD
    xp_gain = found.get("xp_reward", 50)
=======
>>>>>>> 710af19ae02d28a48500c572b4a9ce4c5c947428
    msg = "Quest completed!"

    # Validate proof via DeepSeek
    validation = validate_proof(proof.strip(), found)
    if validation:
        score = validation.get("score", 6)
        if score >= 6:
            pass  # full XP
        elif score >= 3:
<<<<<<< HEAD
            xp_gain = max(1, xp_gain // 2)
            msg = f"Quest completed at half XP — {validation.get('reason', 'proof could be stronger')}"
=======
            msg = f"Quest completed partially — {validation.get('reason', 'proof could be stronger')}"
>>>>>>> 710af19ae02d28a48500c572b4a9ce4c5c947428
        else:
            return False, f"Proof rejected: {validation.get('reason', 'Insufficient effort. Please provide more detail.')}", 0

    found["status"] = "completed"
    found["proof"] = proof.strip()
    found["proof_url"] = proof_url.strip()
    found["proof_file"] = proof_file
    found["completed_at"] = datetime.now().isoformat()

    conn.execute(
        "UPDATE player_profiles SET quests = ?, xp = xp + ? WHERE user_id = ?",
<<<<<<< HEAD
        (json.dumps(quests), xp_gain, user_id),
    )
    conn.commit()

    return True, msg, xp_gain
=======
        (json.dumps(quests) , user_id),
    )
    conn.commit()

    return True, msg
>>>>>>> 710af19ae02d28a48500c572b4a9ce4c5c947428
