import os
import asyncio
import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
from aiohttp import web

from database import (
    init_db,
    create_pending_payment,
    mark_payment_paid,
    mark_agreement_signed,
    get_user_by_reference,
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
KORAPAY_PAYMENT_LINK = os.getenv("KORAPAY_PAYMENT_LINK")

SIGNED_DIR = ensure_signed_dir("signed_agreements")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
init_db()

# ================== START COMMAND ==================
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    reference = f"MBG-{message.from_user.id}-{int(datetime.datetime.now().timestamp())}"

    create_pending_payment(
        telegram_id=message.from_user.id,
        username=message.from_user.username or "N/A",
        reference=reference
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="💳 Pay ₦20,000", url=KORAPAY_PAYMENT_LINK)

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

# ================== AGREEMENT UPLOAD ==================
@dp.message(F.document)
async def receive_agreement(message: types.Message):
    telegram_id = message.from_user.id

    # 1️⃣ Check if payment is confirmed
    if not is_payment_paid(telegram_id):
        await message.reply("⚠️ Payment not confirmed yet. Please complete payment first.")
        return

    # 2️⃣ Check file type
    if not message.document.file_name.lower().endswith(".pdf"):
        await message.reply("❌ Only PDF agreements are allowed.")
        return

    # 3️⃣ Save the PDF locally
    timestamp = int(datetime.datetime.now().timestamp())
    file_name = f"{telegram_id}_{timestamp}.pdf"
    file_path = os.path.join(SIGNED_DIR, file_name)

    # Correct Aiogram v3 download
    await message.document.download(destination_file=file_path)

    # 4️⃣ Mark agreement as signed in DB
    mark_agreement_signed(telegram_id)

    # 5️⃣ Send confirmation to user
    await message.reply(
        "✅ Agreement received successfully!\n\n"
        f"🔗 Register on Naira Trader:\n{NAIRA_TRADER_LINK}\n\n"
        f"👥 Join our private group:\n{PRIVATE_GROUP_LINK}"
    )

    # 6️⃣ Notify admin
    await bot.send_message(
        ADMIN_CHAT_ID,
        f"📄 New agreement uploaded\n"
        f"User: @{message.from_user.username or 'N/A'}\n"
        f"File: {file_path}"
    )

# ================== KORAPAY WEBHOOK ==================
async def korapay_webhook(request):
    try:
        body = await request.json()
        print("🔥 Webhook received:", body)
    except Exception as e:
        print("⚠️ Failed to parse webhook:", e)
        return web.Response(text="bad request", status=400)

    # Only process successful charges
    if body.get("event") != "charge.success":
        return web.Response(text="ignored")

    data = body.get("data", {})
    reference = data.get("reference")
    amount = float(data.get("amount", 0))

    if amount < 20000:
        print("❌ Amount too low:", amount)
        return web.Response(text="invalid amount")

    user = get_user_by_reference(reference)
    if not user:
        print("⚠️ Reference not found:", reference)
        return web.Response(text="reference not found")

    mark_payment_paid(reference)

    await bot.send_message(
        user["telegram_id"],
        "✅ *Payment confirmed automatically!*\n\n"
        "Please upload your signed service agreement PDF to continue.",
        parse_mode="Markdown"
    )

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
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
