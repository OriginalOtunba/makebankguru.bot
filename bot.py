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
    get_user_by_telegram_id,
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
        "💸 MakeBankGuru Trading Support Service 💸
Powered by MakeBankGuru | Naira Trader Affiliate Partner

This service is designed exclusively for clients who open their Naira Trading account through our affiliate link.

💼 What We Provide 

This is a digital trading assistance service, offering:
 • Market analysis support
 • Strategy implementation guidance
 • Automated trading setup assistance
 • Risk-management parameter configuration
 • Ongoing system optimization based on market conditions

Clients authorize access through read-only or investor-level credentials, which allows our system to apply the user-selected trading strategy on their behalf.

No deposit access. No withdrawal access. No fund management.

💳 Service Structure

To activate your trading support package:
 1. Pay the ₦20,000 setup /service fee via our secure payment link.
 2. Complete payment verification inside our Telegram bot @makebankguru_bot .
 3. Sign and upload the digital service agreement.
 4. Choose your preferred trading approach.
 5. Our system will apply your selected strategy using your investor access.

📊 Performance-Based Support Fee

When clients withdraw profits generated based on their selected strategy, a 20% support fee is charged.
This is billed as a “performance-based technical support fee”, not a profit split.

You retain 80% of performance.
We charge 20% for ongoing monitoring, optimization, and strategy maintenance.

🛡️ Safety & Control

 • We never request deposit/withdrawal permissions.
 • Only investor-level authorization is used.
 • You retain full control of your account at all times.
 • All processes are agreement-based and transparent.

📄 Disclaimer 

This is not an investment service and we do not provide financial returns, guarantees, or capital growth promises.
Users choose their own trading strategies, and market performance may vary.
By using our service, clients accept all market-related risks.

🚀 Getting Started

After payment, you’ll receive access to:
 • Affiliate registration link
 • Private group
 • Automated onboarding bot
 • Service agreement upload
 • Strategy setup assistance

Add-On

If you’re not ready for the full service, join our Free Daily Signal Channel for educational trade ideas and market insights."
        "To activate your Trading Support Service:\n"
        "1️⃣ Complete payment\n"
        "2️⃣ Gain Access to our Top 3 Strategies\n"
        "3️⃣ Upload signed agreement\n\n"
        "After verification, select your strategy .",
        parse_mode="Markdown",
        reply_markup=kb.as_markup()
    )

# ================== STATUS COMMAND ==================
@dp.message(Command("status"))
async def status_cmd(message: types.Message):
    telegram_id = message.from_user.id
    
    # Check if payment is verified
    if not is_payment_paid(telegram_id):
        await message.answer(
            "⚠️ *Payment Status: Not Verified*\n\n"
            "Please complete your payment first.\n"
            "Use /start to get the payment link.",
            parse_mode="Markdown"
        )
        return
    
    # Check if agreement is signed
    from database import get_user_by_telegram_id
    user = get_user_by_telegram_id(telegram_id)
    
    if user and user['agreement_signed']:
        await message.answer(
            "✅ *Status: Fully Activated*\n\n"
            f"🔗 Register for your Naira Trading Account:\n{NAIRA_TRADER_LINK}\n\n"
            f"👥 Join the Elite Group:\n{PRIVATE_GROUP_LINK}",
            parse_mode="Markdown"
        )
    else:
        kb = InlineKeyboardBuilder()
        kb.button(text="📄 Download Agreement Template", url=AGREEMENT_LINK)
        kb.adjust(1)
        
        await message.answer(
            "✅ *Payment: Verified*\n"
            "⏳ *Agreement: Pending*\n\n"
            "📋 *Next Step: Upload Signed Agreement*\n\n"
            "1️⃣ Download the agreement template below\n"
            "2️⃣ Fill in your details and sign it\n"
            "3️⃣ Scan/photograph and convert to PDF\n"
            "4️⃣ Send the PDF file here in this chat\n\n"
            "⚠️ *Important:* Only PDF files are accepted.",
            parse_mode="Markdown",
            reply_markup=kb.as_markup()
        )

# ================== HELP COMMAND ==================
@dp.message(Command("help"))
async def help_cmd(message: types.Message):
    await message.answer(
        "ℹ️ *MakeBankGuru Bot Help*\n\n"
        "*Available Commands:*\n"
        "/start - Begin registration & payment\n"
        "/status - Check your activation status\n"
        "/help - Show this help message\n\n"
        "*How It Works:*\n"
        "1️⃣ Use /start to get your payment link\n"
        "2️⃣ Pay ₦20,000 via the link\n"
        "3️⃣ Payment is auto-verified\n"
        "4️⃣ Upload your signed agreement PDF\n"
        "5️⃣ Get access to Naira Trader Top 3 Strategies & Elite Group\n\n"
        "*Need Support?*\n"
        "Contact: @MakeBankGuru",
        parse_mode="Markdown"
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
        kb = InlineKeyboardBuilder()
        kb.button(text="💳 Make Payment", url=f"{KORAPAY_BASE_LINK}?amount=20000")
        
        await message.reply(
            "⚠️ *Payment Not Confirmed*\n\n"
            "Please complete your payment first before uploading the agreement.\n\n"
            "Use /start to get your payment link.",
            parse_mode="Markdown",
            reply_markup=kb.as_markup()
        )
        return

    # Validate PDF
    if not message.document.file_name.lower().endswith(".pdf"):
        await message.reply(
            "❌ *Invalid File Format*\n\n"
            "Only PDF files are accepted.\n\n"
            "Please convert your agreement to PDF and try again."
        )
        return

    # Show processing message
    processing_msg = await message.reply("⏳ Processing your agreement...")

    try:
        # Download file (Aiogram 3.x method)
        timestamp = int(datetime.datetime.now().timestamp())
        file_name = f"{telegram_id}_{timestamp}.pdf"
        file_path = os.path.join(SIGNED_DIR, file_name)

        file = await bot.get_file(message.document.file_id)
        await bot.download_file(file.file_path, file_path)

        # Mark as signed
        mark_agreement_signed(telegram_id)

        # Delete processing message
        await processing_msg.delete()

        # Send success message with next steps
        await message.reply(
            "✅ *Agreement Received Successfully!*\n\n"
            "🎉 Your account is now fully activated!\n\n"
            "📌 *Next Steps:*\n\n"
            f"1️⃣ Register for a  Naira Trading account:\n{NAIRA_TRADER_LINK}\n\n"
            f"2️⃣ Join our Elite Group:\n{PRIVATE_GROUP_LINK}\n\n"
            "Welcome to MakeBankGuru! 🚀",
            parse_mode="Markdown"
        )

        # Notify admin
        await bot.send_document(
            ADMIN_CHAT_ID,
            types.FSInputFile(file_path),
            caption=f"📄 *New Agreement Uploaded*\n\n"
                    f"👤 User: @{message.from_user.username or 'N/A'}\n"
                    f"🆔 Telegram ID: {telegram_id}\n"
                    f"📅 Date: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            parse_mode="Markdown"
        )

    except Exception as e:
        print(f"❌ Error downloading agreement: {e}")
        await processing_msg.delete()
        await message.reply(
            "❌ *Failed to Process Agreement*\n\n"
            "There was an error processing your file.\n"
            "Please try again or contact support."
        )

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

    # Notify user with detailed instructions
    try:
        kb = InlineKeyboardBuilder()
        kb.button(text="📄 Download Agreement Template", url=AGREEMENT_LINK)
        kb.adjust(1)
        
        await bot.send_message(
            user["telegram_id"],
            "✅ *Payment Confirmed Successfully!*\n\n"
            "📋 *Next Step: Upload Signed Agreement*\n\n"
            "1️⃣ Download the agreement template below\n"
            "2️⃣ Fill in your details and sign it\n"
            "3️⃣ Scan/photograph and convert to PDF\n"
            "4️⃣ Send the PDF file here in this chat\n\n"
            "⚠️ *Important:* Only PDF files are accepted.",
            parse_mode="Markdown",
            reply_markup=kb.as_markup()
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



