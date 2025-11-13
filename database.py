import sqlite3
import datetime

DB_PATH = "users.db"

# Initialize the database
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

# Add a new user (or update if exists)
def add_user(user_id, username, payment_ref):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO verified_users
        (user_id, username, payment_ref, date_verified, agreement_accepted, date_agreement_accepted)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, username, payment_ref, datetime.datetime.now().isoformat(), 0, None))
    conn.commit()
    conn.close()

# Mark agreement as accepted with timestamp
def mark_agreement_accepted(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        UPDATE verified_users
        SET agreement_accepted = 1,
            date_agreement_accepted = ?
        WHERE user_id = ?
    """, (datetime.datetime.now().isoformat(), user_id))
    conn.commit()
    conn.close()

# Check if user has verified payment
def is_verified(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM verified_users WHERE user_id=?", (user_id,))
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

# Retrieve full user info for auditing
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
