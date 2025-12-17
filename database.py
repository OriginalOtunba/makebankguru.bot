import sqlite3
import datetime
import os

DB_PATH = "users.db"

# ================== DATABASE INITIALIZATION ==================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Table for verified users and agreements
    c.execute("""
        CREATE TABLE IF NOT EXISTS verified_users (
            telegram_id INTEGER PRIMARY KEY,
            username TEXT,
            payment_reference TEXT,
            payment_status TEXT DEFAULT 'pending', -- pending, paid
            date_payment_verified TEXT,
            agreement_signed INTEGER DEFAULT 0,
            date_agreement_signed TEXT
        )
    """)

    # Table for pending payments tracking
    c.execute("""
        CREATE TABLE IF NOT EXISTS pending_payments (
            payment_reference TEXT PRIMARY KEY,
            telegram_id INTEGER,
            username TEXT,
            amount REAL DEFAULT 20000,
            status TEXT DEFAULT 'pending', -- pending, paid
            date_created TEXT
        )
    """)

    conn.commit()
    conn.close()


# ================== PENDING PAYMENTS ==================
def create_pending_payment(telegram_id: int, username: str, reference: str, amount: float = 20000):
    now = datetime.datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT INTO pending_payments (payment_reference, telegram_id, username, amount, status, date_created)
        VALUES (?, ?, ?, ?, 'pending', ?)
        ON CONFLICT(payment_reference) DO UPDATE SET
            telegram_id=excluded.telegram_id,
            username=excluded.username,
            amount=excluded.amount,
            status='pending',
            date_created=excluded.date_created
    """, (reference, telegram_id, username, amount, now))
    conn.commit()
    conn.close()


# ================== PAYMENT CONFIRMATION ==================
def mark_payment_paid(reference: str):
    now = datetime.datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Update pending payment status
    c.execute("""
        UPDATE pending_payments
        SET status='paid'
        WHERE payment_reference=?
    """, (reference,))

    # Move to verified_users table or update if exists
    c.execute("""
        INSERT INTO verified_users (telegram_id, username, payment_reference, payment_status, date_payment_verified)
        SELECT telegram_id, username, payment_reference, 'paid', ?
        FROM pending_payments
        WHERE payment_reference=?
        ON CONFLICT(telegram_id) DO UPDATE SET
            username=excluded.username,
            payment_reference=excluded.payment_reference,
            payment_status='paid',
            date_payment_verified=excluded.date_payment_verified
    """, (now, reference))

    conn.commit()
    conn.close()


# ================== AGREEMENT SIGNING ==================
def mark_agreement_signed(telegram_id: int):
    now = datetime.datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        UPDATE verified_users
        SET agreement_signed = 1,
            date_agreement_signed = ?
        WHERE telegram_id = ?
    """, (now, telegram_id))
    conn.commit()
    conn.close()


# ================== QUERY HELPERS ==================
def get_user_by_reference(reference: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT telegram_id, username, payment_reference, payment_status, agreement_signed
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
            "agreement_signed": row[4]
        }
    return None


def is_payment_paid(telegram_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        SELECT payment_status FROM verified_users WHERE telegram_id=?
    """, (telegram_id,))
    row = c.fetchone()
    conn.close()
    return row and row[0] == "paid"


# ================== PDF HANDLER SUPPORT ==================
# This helper ensures the folder for signed agreements exists
def ensure_signed_dir(directory="signed_agreements"):
    os.makedirs(directory, exist_ok=True)
    return directory
