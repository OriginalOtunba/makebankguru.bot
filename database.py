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
    print("✅ Database initialized successfully")


# ================== DIRECTORY ==================
def ensure_signed_dir(path):
    os.makedirs(path, exist_ok=True)
    return path


# ================== CREATE PENDING PAYMENT ==================
def create_pending_payment(telegram_id: int, username: str, reference: str):
    now = datetime.datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    try:
        c.execute("""
            INSERT OR REPLACE INTO pending_payments
            (telegram_id, username, payment_reference, status, date_created)
            VALUES (?, ?, ?, 'pending', ?)
        """, (telegram_id, username, reference, now))

        conn.commit()
        print(f"✅ Pending payment created - User: {telegram_id}, Ref: {reference}")
    except Exception as e:
        print(f"❌ Error creating pending payment: {e}")
        conn.rollback()
    finally:
        conn.close()


# ================== MARK PAYMENT PAID ==================
def mark_payment_paid(reference: str):
    now = datetime.datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    try:
        # First, get the pending payment info
        c.execute("""
            SELECT telegram_id, username FROM pending_payments
            WHERE payment_reference=?
        """, (reference,))
        
        pending = c.fetchone()
        
        if not pending:
            print(f"⚠️ No pending payment found for reference: {reference}")
            conn.close()
            return False

        telegram_id, username = pending

        # Update pending payments status
        c.execute("""
            UPDATE pending_payments
            SET status='paid'
            WHERE payment_reference=?
        """, (reference,))

        # Insert or update verified_users
        c.execute("""
            INSERT INTO verified_users 
            (telegram_id, username, payment_reference, payment_status, date_payment_verified)
            VALUES (?, ?, ?, 'paid', ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                payment_reference=excluded.payment_reference,
                payment_status='paid',
                date_payment_verified=excluded.date_payment_verified
        """, (telegram_id, username, reference, now))

        conn.commit()
        print(f"✅ Payment marked as paid - User: {telegram_id}, Ref: {reference}")
        return True
        
    except Exception as e:
        print(f"❌ Error marking payment paid: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


# ================== MARK AGREEMENT SIGNED ==================
def mark_agreement_signed(telegram_id: int):
    now = datetime.datetime.now().isoformat()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    try:
        c.execute("""
            UPDATE verified_users
            SET agreement_signed=1,
                date_agreement_signed=?
            WHERE telegram_id=?
        """, (now, telegram_id))

        conn.commit()
        
        if c.rowcount > 0:
            print(f"✅ Agreement signed - User: {telegram_id}")
            return True
        else:
            print(f"⚠️ User not found in verified_users: {telegram_id}")
            return False
            
    except Exception as e:
        print(f"❌ Error marking agreement signed: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()


# ================== CHECK PAYMENT STATUS ==================
def is_payment_paid(telegram_id: int) -> bool:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    try:
        c.execute("""
            SELECT payment_status FROM verified_users WHERE telegram_id=?
        """, (telegram_id,))
        row = c.fetchone()
        
        result = row is not None and row[0] == "paid"
        print(f"🔍 Payment check - User: {telegram_id}, Paid: {result}")
        return result
        
    except Exception as e:
        print(f"❌ Error checking payment status: {e}")
        return False
    finally:
        conn.close()


# ================== GET USER BY REFERENCE ==================
def get_user_by_reference(reference: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    try:
        # First check verified_users
        c.execute("""
            SELECT telegram_id, username, payment_reference, payment_status, 
                   agreement_signed, date_agreement_signed
            FROM verified_users
            WHERE payment_reference=?
        """, (reference,))
        row = c.fetchone()

        # If not found in verified_users, check pending_payments
        if not row:
            c.execute("""
                SELECT telegram_id, username, payment_reference, status, 0, NULL
                FROM pending_payments
                WHERE payment_reference=?
            """, (reference,))
            row = c.fetchone()

        if row:
            user_data = {
                "telegram_id": row[0],
                "username": row[1],
                "payment_reference": row[2],
                "payment_status": row[3],
                "agreement_signed": row[4],
                "date_agreement_signed": row[5]
            }
            print(f"✅ User found - Ref: {reference}, ID: {row[0]}")
            return user_data
        else:
            print(f"⚠️ No user found for reference: {reference}")
            return None
            
    except Exception as e:
        print(f"❌ Error getting user by reference: {e}")
        return None
    finally:
        conn.close()


# ================== GET USER BY TELEGRAM ID ==================
def get_user_by_telegram_id(telegram_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    try:
        c.execute("""
            SELECT telegram_id, username, payment_reference, payment_status, 
                   agreement_signed, date_agreement_signed
            FROM verified_users
            WHERE telegram_id=?
        """, (telegram_id,))
        row = c.fetchone()

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
        
    except Exception as e:
        print(f"❌ Error getting user by telegram ID: {e}")
        return None
    finally:
        conn.close()


# ================== GET ALL VERIFIED USERS (ADMIN) ==================
def get_all_verified_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    try:
        c.execute("""
            SELECT telegram_id, username, payment_reference, payment_status, 
                   agreement_signed, date_payment_verified, date_agreement_signed
            FROM verified_users
            ORDER BY date_payment_verified DESC
        """)
        rows = c.fetchall()
        
        users = []
        for row in rows:
            users.append({
                "telegram_id": row[0],
                "username": row[1],
                "payment_reference": row[2],
                "payment_status": row[3],
                "agreement_signed": row[4],
                "date_payment_verified": row[5],
                "date_agreement_signed": row[6]
            })
        
        return users
        
    except Exception as e:
        print(f"❌ Error getting all verified users: {e}")
        return []
    finally:
        conn.close()


# ================== GET STATS (ADMIN) ==================
def get_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    try:
        # Total pending payments
        c.execute("SELECT COUNT(*) FROM pending_payments WHERE status='pending'")
        pending_count = c.fetchone()[0]
        
        # Total paid
        c.execute("SELECT COUNT(*) FROM verified_users WHERE payment_status='paid'")
        paid_count = c.fetchone()[0]
        
        # Total agreements signed
        c.execute("SELECT COUNT(*) FROM verified_users WHERE agreement_signed=1")
        signed_count = c.fetchone()[0]
        
        return {
            "pending_payments": pending_count,
            "paid_users": paid_count,
            "signed_agreements": signed_count
        }
        
    except Exception as e:
        print(f"❌ Error getting stats: {e}")
        return {
            "pending_payments": 0,
            "paid_users": 0,
            "signed_agreements": 0
        }
    finally:
        conn.close()
