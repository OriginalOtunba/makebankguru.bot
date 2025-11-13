import sqlite3

DB_PATH = "users.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS verified_users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            payment_ref TEXT,
            date_verified TEXT
        )
    """)
    conn.commit()
    conn.close()

def add_user(user_id, username, payment_ref, date_verified):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO verified_users VALUES (?, ?, ?, ?)",
              (user_id, username, payment_ref, date_verified))
    conn.commit()
    conn.close()

def is_verified(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM verified_users WHERE user_id=?", (user_id,))
    exists = c.fetchone() is not None
    conn.close()
    return exists
