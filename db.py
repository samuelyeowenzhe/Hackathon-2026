import sqlite3
import os

DATABASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lifequest.db")

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'candidate',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS player_profiles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
<<<<<<< HEAD
            level INTEGER DEFAULT 1,
            xp INTEGER DEFAULT 0,
            xp_to_next INTEGER DEFAULT 100,
            hp INTEGER DEFAULT 100,
            max_hp INTEGER DEFAULT 100,
=======
>>>>>>> 710af19ae02d28a48500c572b4a9ce4c5c947428
            skills TEXT DEFAULT '[]',
            cv_data TEXT DEFAULT '{}',
            char_class TEXT DEFAULT 'Warrior',
            quests TEXT DEFAULT '[]',
<<<<<<< HEAD
            title TEXT DEFAULT 'Adventurer',
=======
            title TEXT DEFAULT 'Job title',
>>>>>>> 710af19ae02d28a48500c572b4a9ce4c5c947428
            avatar TEXT DEFAULT '',
            last_login TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            skill_required TEXT,
<<<<<<< HEAD
            xp_reward INTEGER DEFAULT 50,
            hp_cost INTEGER DEFAULT 10,
            boss_name TEXT DEFAULT 'Unknown',
=======
>>>>>>> 710af19ae02d28a48500c572b4a9ce4c5c947428
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            active INTEGER DEFAULT 1
        );
<<<<<<< HEAD
        CREATE TABLE IF NOT EXISTS bosses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_id INTEGER,
            name TEXT NOT NULL,
            description TEXT,
            min_level INTEGER DEFAULT 1,
            hp INTEGER DEFAULT 50,
            xp_reward INTEGER DEFAULT 30,
            skill_requirements TEXT DEFAULT '[]',
            challenge_data TEXT DEFAULT '{}',
            FOREIGN KEY (event_id) REFERENCES events(id)
        );
        CREATE TABLE IF NOT EXISTS battle_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            player_id INTEGER,
            boss_id INTEGER,
            won INTEGER DEFAULT 0,
            xp_gained INTEGER DEFAULT 0,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (player_id) REFERENCES users(id),
            FOREIGN KEY (boss_id) REFERENCES bosses(id)
        );
=======
>>>>>>> 710af19ae02d28a48500c572b4a9ce4c5c947428
        CREATE TABLE IF NOT EXISTS friend_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            from_user INTEGER NOT NULL,
            to_user INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (from_user) REFERENCES users(id),
            FOREIGN KEY (to_user) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS employers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            company_name TEXT NOT NULL,
            industry TEXT DEFAULT '',
            website TEXT DEFAULT '',
            description TEXT DEFAULT '',
            contact_email TEXT DEFAULT '',
            logo TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS universities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            university_name TEXT DEFAULT '',
            university_type TEXT DEFAULT '',
            university_website TEXT DEFAULT '',
            university_email TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS job_listings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employer_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            skills_required TEXT DEFAULT '[]',
            location TEXT DEFAULT '',
            salary_range TEXT DEFAULT '',
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (employer_id) REFERENCES employers(id)
        );
        CREATE TABLE IF NOT EXISTS employer_swipes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employer_id INTEGER NOT NULL,
            candidate_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(employer_id, candidate_id),
            FOREIGN KEY (employer_id) REFERENCES employers(id),
            FOREIGN KEY (candidate_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS hires (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            candidate_id INTEGER NOT NULL,
            employer_id INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES job_listings(id),
            FOREIGN KEY (candidate_id) REFERENCES users(id),
            FOREIGN KEY (employer_id) REFERENCES employers(id)
        );
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        );
    """)
    conn.commit()
    conn.close()