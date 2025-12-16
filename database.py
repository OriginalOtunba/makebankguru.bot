import sqlite3
import datetime

DB_PATH = "users.db"

# Ensure table for pending payments exists
def init_pending_payments_table():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS pending_payments (
            payment_ref TEXT PRIMARY KEY,
            user_id INTEGER,
            username TEXT,
            amount REAL,
            status TEXT DEFAULT 'pending', -- pending, verified, failed
            date_created TEXT
        )
    """)
    conn.commit()
    conn.close()

# Create a pending payment before Korapay confirms it
def create_pending_payment(user_id, username, payment_ref, amount):
    now = datetime.datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO pending_payments (payment_ref, user_id, username, amount, status, date_created)
        VALUES (?, ?, ?, ?, 'pending', ?)
        ON CONFLICT(payment_ref) DO UPDATE SET
            user_id = excluded.user_id,
            username = excluded.username,
            amount = excluded.amount,
            status = 'pending',
            date_created = excluded.date_created
    """, (payment_ref, user_id, username, amount, now))
    conn.commit()
    conn.close()
    print(f"Pending payment created for user {user_id} with ref {payment_ref}")
