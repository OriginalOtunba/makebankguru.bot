import os
import asyncio
import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
from aiohttp import web
from urllib.parse import quote_plus

from database import (
    init_db,
    create_pending_payment,
    mark_payment_paid,
    mark_agreement_signed,
    get_user_by_reference,
    get_user_by_korapay_reference,
    is_payment_paid,
    ensure_signed_dir
)

# ================== CONFIG ==================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))
NAIRA_TRADER_LINK = os.getenv("NAIRA_TRADER_LINK")
PRIVATE_GROUP_LINK = os.getenv("PRIVATE_GROUP_LINK")
AGREEMENT_LINK = os.getenv("AGREEMENT_LINK")
KORAPAY_BASE_LINK = os.getenv("KORAPAY_PAYMENT_LINK")

SIGNED_DIR = ensure_signed_dir("signed_agreements")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
init_db()

# ================== START COMMAND ==================
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    telegram_id = message.from_user.id
    username = message.from_user.username or "N/A"
    timestamp = int(datetime.datetime.now().timestamp())
    reference = f"MBG-{telegram_id}-{timestamp}"

    # Store pending payment in DB
    create_pending_payment(
        telegram_id=telegram_id,
        username=username,
        reference=reference
    )

    # Build Korapay payment link
    korapay_link = f"{KORAPAY_BASE_LINK}?amount=20000&reference={quote_plus(reference)}"

    kb = InlineKeyboardBuilder()
    kb.button(text="💳 Pay ₦20,000", url=korapay_link)

    await message.answer(
        "👋 *Welcome to MakeBankGuru*\n\n"
        "To activate your Trading Support Service:\n"
        "1️⃣ Complete payment\n"
        "2️⃣ Payment is auto-confirmed\n"
        "3️⃣ Upload agreement\n\n"
        "No manual verification required.",
        parse_mode="Markdown",
        reply_markup=kb.as_markup()
    )

# ================== ADMIN COMMANDS ==================
@dp.message(Command("stats"))
async def stats_cmd(message: types.Message):
    if message.from_user.id != ADMIN_CHAT_ID:
        return
    
    from database import get_stats
    stats = get_stats()
    
    await message.answer(
        f"📊 *Bot Statistics*\n\n"
        f"⏳ Pending Payments: {stats['pending_payments']}\n"
        f"✅ Paid Users: {stats['paid_users']}\n"
        f"📄 Signed Agreements: {stats['signed_agreements']}",
        parse_mode="Markdown"
    )

@dp.message(Command("users"))
async def users_cmd(message: types.Message):
    if message.from_user.id != ADMIN_CHAT_ID:
        return
    
    from database import get_all_verified_users
    users = get_all_verified_users()
    
    if not users:
        await message.answer("No verified users yet.")
        return
    
    response = "👥 *Verified Users*\n\n"
    for user in users[:10]:  # Show first 10
        status = "✅ Signed" if user['agreement_signed'] else "⏳ Pending Agreement"
        response += f"• @{user['username']} (ID: {user['telegram_id']}) - {status}\n"
    
    if len(users) > 10:
        response += f"\n_Showing 10 of {len(users)} users_"
    
    await message.answer(response, parse_mode="Markdown")

# ================== AGREEMENT UPLOAD ==================
@dp.message(F.document)
async def receive_agreement(message: types.Message):
    telegram_id = message.from_user.id

    # Check payment status
    if not is_payment_paid(telegram_id):
        await message.reply("⚠️ Payment not confirmed yet. Please complete payment first.")
        return

    # Validate PDF
    if not message.document.file_name.lower().endswith(".pdf"):
        await message.reply("❌ Only PDF agreements are allowed.")
        return

    try:
        # Download file (FIXED for Aiogram 3.x)
        timestamp = int(datetime.datetime.now().timestamp())
        file_name = f"{telegram_id}_{timestamp}.pdf"
        file_path = os.path.join(SIGNED_DIR, file_name)

        # Correct method for Aiogram 3.x
        file = await bot.get_file(message.document.file_id)
        await bot.download_file(file.file_path, file_path)

        # Mark as signed
        mark_agreement_signed(telegram_id)

        await message.reply(
            "✅ Agreement received successfully!\n\n"
            f"🔗 Register on Naira Trader:\n{NAIRA_TRADER_LINK}\n\n"
            f"👥 Join our private group:\n{PRIVATE_GROUP_LINK}"
        )

        # Notify admin
        await bot.send_message(
            ADMIN_CHAT_ID,
            f"📄 New agreement uploaded\n"
            f"User: @{message.from_user.username or 'N/A'}\n"
            f"Telegram ID: {telegram_id}\n"
            f"File: {file_path}"
        )

    except Exception as e:
        print(f"❌ Error downloading agreement: {e}")
        await message.reply("❌ Failed to process agreement. Please try again.")

# ================== KORAPAY WEBHOOK ==================
async def korapay_webhook(request):
    try:
        body = await request.json()
        print("🔥 Webhook received:", body)
    except Exception as e:
        print(f"⚠️ Failed to parse webhook: {e}")
        return web.Response(text="bad request", status=400)

    # Validate event type
    if body.get("event") != "charge.success":
        print(f"⚠️ Ignored event: {body.get('event')}")
        return web.Response(text="ignored")

    data = body.get("data", {})
    korapay_reference = data.get("reference") or data.get("payment_reference")
    amount = float(data.get("amount", 0))

    print(f"💰 Payment - Korapay Reference: {korapay_reference}, Amount: {amount}")

    # Validate amount
    if amount < 20000:
        print(f"❌ Amount too low: {amount}")
        return web.Response(text="invalid amount")

    # Find user by Korapay reference
    user = get_user_by_korapay_reference(korapay_reference)
    
    # If not found, try to match by timing (last pending payment)
    if not user:
        print(f"⚠️ No direct match for Korapay ref: {korapay_reference}")
        print("🔍 Attempting to match by recent pending payment...")
        
        # This is a fallback - matches the most recent pending payment
        from database import get_most_recent_pending_payment
        user = get_most_recent_pending_payment()
        
        if user:
            print(f"✅ Matched to recent pending payment: User {user['telegram_id']}")

    if not user:
        print(f"❌ Could not match payment to any user")
        return web.Response(text="user not found")

    # Mark payment as paid with Korapay reference
    mark_payment_paid(korapay_reference, user.get("payment_reference"))
    print(f"✅ Payment marked as paid for user: {user['telegram_id']}")

    # Notify user
    try:
        await bot.send_message(
            user["telegram_id"],
            "✅ *Payment confirmed automatically!*\n\n"
            "Please upload your signed service agreement PDF to continue.",
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"❌ Failed to notify user {user['telegram_id']}: {e}")

    return web.Response(text="ok")

# ================== WEB SERVER ==================
async def handle_root(request):
    return web.Response(text="MakeBankGuru Bot Running ✔️")

async def start_webserver():
    app = web.Application()
    app.add_routes([
        web.get("/", handle_root),
        web.post("/korapay-webhook", korapay_webhook)
    ])

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌍 Webserver running on port {port}")

# ================== MAIN ==================
async def main():
    await start_webserver()
    print("✅ Bot started successfully")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
