import os
import asyncio
import aiohttp
import datetime
import sqlite3
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
from aiohttp import web

# ================== CONFIG ==================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))
KORA_SECRET_KEY = os.getenv("KORA_SECRET_KEY")

NAIRA_TRADER_LINK = os.getenv("NAIRA_TRADER_LINK")
PRIVATE_GROUP_LINK = os.getenv("PRIVATE_GROUP_LINK")
AGREEMENT_LINK = os.getenv("AGREEMENT_LINK")
KORAPAY_PAYMENT_LINK = os.getenv("KORAPAY_PAYMENT_LINK")

PORT = int(os.environ.get("PORT", 10000))
SIGNED_DIR = "signed_agreements"
DB_PATH = "payments.db"

EXPECTED_AMOUNT = 20000
CURRENCY = "NGN"

# ================== INIT ==================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
os.makedirs(SIGNED_DIR, exist_ok=True)

# ================== DATABASE ==================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS pending_payments (
        user_id INTEGER,
        username TEXT,
        status TEXT,
        created_at TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS completed_payments (
        user_id INTEGER,
        reference TEXT,
        amount REAL,
        currency TEXT,
        paid_at TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS agreements (
        user_id INTEGER,
        file_path TEXT,
        signed_at TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS payment_anomalies (
        reference TEXT,
        payload TEXT,
        logged_at TEXT
    )
    """)

    conn.commit()
    conn.close()

init_db()

# ================== HELPERS ==================
def add_pending(user: types.User):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO pending_payments VALUES (?, ?, ?, ?)",
        (user.id, user.username, "pending", datetime.datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()

def mark_paid(user_id, reference, amount, currency):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        "INSERT INTO completed_payments VALUES (?, ?, ?, ?, ?)",
        (user_id, reference, amount, currency, datetime.datetime.utcnow().isoformat())
    )

    c.execute(
        "UPDATE pending_payments SET status = 'paid' WHERE user_id = ?",
        (user_id,)
    )

    conn.commit()
    conn.close()

def has_paid(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM completed_payments WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def has_signed(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT 1 FROM agreements WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    return result is not None

def log_anomaly(reference, payload):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO payment_anomalies VALUES (?, ?, ?)",
        (reference, str(payload), datetime.datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()

# ================== BOT HANDLERS ==================
@dp.message(Command("start"))
async def start(message: types.Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="💳 Activate Trading Support", callback_data="pay")

    await message.answer(
        "💸 *MakeBankGuru Trading Support*\n\n"
        "Secure onboarding. Automated verification.\n\n"
        "Click below to activate your support package.",
        parse_mode="Markdown",
        reply_markup=kb.as_markup()
    )

@dp.callback_query(F.data == "pay")
async def initiate_payment(callback: types.CallbackQuery):
    add_pending(callback.from_user)

    await callback.message.edit_text(
        f"💳 *Payment Step*\n\n"
        f"Service Fee: ₦{EXPECTED_AMOUNT}\n\n"
        f"👉 [Pay via Korapay]({KORAPAY_PAYMENT_LINK})\n\n"
        f"Once payment is completed, access will unlock automatically.",
        parse_mode="Markdown"
    )

# ================== AGREEMENT UPLOAD ==================
@dp.message(F.document)
async def receive_agreement(message: types.Message):
    if not has_paid(message.from_user.id):
        await message.reply("⚠️ Payment not yet confirmed.")
        return

    if has_signed(message.from_user.id):
        await message.reply("✅ Agreement already received.")
        return

    if not message.document.file_name.lower().endswith(".pdf"):
        await message.reply("❌ PDF files only.")
        return

    timestamp = int(datetime.datetime.utcnow().timestamp())
    path = f"{SIGNED_DIR}/{message.from_user.id}_{timestamp}.pdf"

    file = await bot.get_file(message.document.file_id)
    await file.download_to_drive(path)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO agreements VALUES (?, ?, ?)",
        (message.from_user.id, path, datetime.datetime.utcnow().isoformat())
    )
    conn.commit()
    conn.close()

    await message.reply(
        "✅ Agreement received.\n\n"
        f"🔗 Naira Trader: {NAIRA_TRADER_LINK}\n"
        f"👥 Private Group: {PRIVATE_GROUP_LINK}"
    )

    await bot.send_message(
        ADMIN_CHAT_ID,
        f"📄 Agreement uploaded by @{message.from_user.username}\nFile: {path}"
    )

# ================== KORAPAY WEBHOOK ==================
async def korapay_webhook(request):
    payload = await request.json()
    event = payload.get("event")
    data = payload.get("data", {})

    reference = data.get("reference")
    amount = data.get("amount")
    currency = data.get("currency")

    if event != "charge.success":
        return web.Response(text="ignored")

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT user_id FROM pending_payments WHERE status='pending' ORDER BY created_at DESC LIMIT 1")
    row = c.fetchone()
    conn.close()

    if not row or currency != CURRENCY or amount < EXPECTED_AMOUNT:
        log_anomaly(reference, payload)
        return web.Response(text="logged")

    user_id = row[0]
    mark_paid(user_id, reference, amount, currency)

    await bot.send_message(
        user_id,
        "🎉 Payment confirmed!\n\n"
        "Please upload your signed service agreement PDF to continue.\n"
        f"🧾 {AGREEMENT_LINK}"
    )

    return web.Response(text="ok")

# ================== WEB SERVER ==================
async def start_webserver():
    app = web.Application()
    app.add_routes([
        web.get("/", lambda r: web.Response(text="Bot Alive")),
        web.post("/korapay-webhook", korapay_webhook)
    ])

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

# ================== MAIN ==================
async def main():
    await start_webserver()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
