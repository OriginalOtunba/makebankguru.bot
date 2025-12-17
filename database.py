import sqlite3
import datetime
import os

DB_PATH = "users.db"
SIGNED_DIR = "signed_agreements"


# ================== DATABASE INIT ==================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Table for pending payments
    c.execute("""
        CREATE TABLE IF NOT EXISTS pending_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            username TEXT,
            payment_reference TEXT UNIQUE,
            status TEXT DEFAULT 'pending',
            date_created TEXT
        )
    """)

    # Table for verified users
    c.execute("""
        CREATE TABLE IF NOT EXISTS verified_users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            payment_reference TEXT,
            payment_status TEXT DEFAULT 'pending',
            date_payment_verified TEXT,
            agreement_signed INTEGER DEFAULT 0,
            date_agreement_signed TEXT
        )
    """)

    conn.commit()
    conn.close()


# ================== DIRECTORY ==================
def ensure_signed_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


# ================== CREATE PENDING PAYMENT ==================
def create_pending_payment(telegram_id: int, username: str, reference: str):
    now = datetime.datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        INSERT OR REPLACE INTO pending_payments
        (telegram_id, username, payment_reference, date_created)
        VALUES (?, ?, ?, ?)
    """, (telegram_id, username, reference, now))

    conn.commit()
    conn.close()


# ================== MARK PAYMENT PAID ==================
def mark_payment_paid(reference: str):
    now = datetime.datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Update pending payments
    c.execute("""
        UPDATE pending_payments
        SET status='paid'
        WHERE payment_reference=?
    """, (reference,))

    # Insert or update verified_users
    c.execute("""
        INSERT INTO verified_users (telegram_id, username, payment_reference, payment_status, date_payment_verified)
        SELECT telegram_id, username, payment_reference, 'paid', ?
        FROM pending_payments
        WHERE payment_reference=?
        ON CONFLICT(telegram_id) DO UPDATE SET
            payment_reference=excluded.payment_reference,
            payment_status='paid',
            date_payment_verified=excluded.date_payment_verified
    """, (now, reference))

    conn.commit()
    conn.close()


# ================== MARK AGREEMENT SIGNED ==================
def mark_agreement_signed(telegram_id: int):
    now = datetime.datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        UPDATE verified_users
        SET agreement_signed=1,
            date_agreement_signed=?
        WHERE telegram_id=?
    """, (now, telegram_id))

    conn.commit()
    conn.close()


# ================== CHECK PAYMENT STATUS ==================
def is_payment_paid(telegram_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT payment_status FROM verified_users WHERE telegram_id=?
    """, (telegram_id,))
    row = c.fetchone()
    conn.close()
    return row is not None and row[0] == "paid"


# ================== GET USER BY REFERENCE ==================
def get_user_by_reference(reference: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT telegram_id, username, payment_reference, payment_status, agreement_signed, date_agreement_signed
        FROM verified_users
        WHERE payment_reference=?
    """, (reference,))
    row = c.fetchone()
    conn.close()

    if row:
        return {
            "telegram_id": row[0],
            "username": row[1],
            "payment_reference": row[2],
            "payment_status": row[3],
            "agreement_signed": row[4],
            "date_agreement_signed": row[5]
        }
    return None
