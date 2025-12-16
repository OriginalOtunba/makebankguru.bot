import sqlite3
import datetime

DB_PATH = "users.db"

# Initialize database
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS verified_users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            payment_ref TEXT,
            date_verified TEXT,
            agreement_accepted INTEGER DEFAULT 0,
            date_agreement_accepted TEXT
        )
    """)
    conn.commit()
    conn.close()

# Add or update a user after successful webhook payment
def unlock_user(user_id, username, payment_ref):
    now = datetime.datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO verified_users (user_id, username, payment_ref, date_verified)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            username = excluded.username,
            payment_ref = excluded.payment_ref,
            date_verified = excluded.date_verified
    """, (user_id, username, payment_ref, now))
    conn.commit()
    conn.close()
    print(f"User {user_id} unlocked at {now}")

# Mark agreement as accepted
def accept_agreement(user_id):
    now = datetime.datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        UPDATE verified_users
        SET agreement_accepted = 1,
            date_agreement_accepted = ?
        WHERE user_id = ?
    """, (now, user_id))
    conn.commit()
    conn.close()
    print(f"User {user_id} accepted agreement at {now}")

# Check if user is verified (payment received)
def is_verified(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM verified_users WHERE user_id=?", (user_id,))
    exists = c.fetchone() is not None
    conn.close()
    return exists

# Check if user has accepted agreement
def has_accepted_agreement(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT agreement_accepted FROM verified_users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row and row[0] == 1

# Retrieve user info for auditing
def get_user_info(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT user_id, username, payment_ref, date_verified, agreement_accepted, date_agreement_accepted
        FROM verified_users
        WHERE user_id=?
    """, (user_id,))
    row = c.fetchone()
    conn.close()
    return row
