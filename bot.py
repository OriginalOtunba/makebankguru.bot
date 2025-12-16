import os
import asyncio
import aiohttp
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
    is_payment_paid
)

# ================== CONFIG ==================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID"))
NAIRA_TRADER_LINK = os.getenv("NAIRA_TRADER_LINK")
PRIVATE_GROUP_LINK = os.getenv("PRIVATE_GROUP_LINK")
AGREEMENT_LINK = os.getenv("AGREEMENT_LINK")
KORAPAY_PAYMENT_LINK = os.getenv("KORAPAY_PAYMENT_LINK")

SIGNED_DIR = "signed_agreements"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
init_db()
os.makedirs(SIGNED_DIR, exist_ok=True)

# ================== START ==================
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
    if not is_payment_paid(message.from_user.id):
        await message.reply("⚠️ Payment not confirmed yet.")
        return

    if not message.document.file_name.lower().endswith(".pdf"):
        await message.reply("❌ Only PDF agreements allowed.")
        return

    timestamp = int(datetime.datetime.now().timestamp())
    path = os.path.join(SIGNED_DIR, f"{message.from_user.id}_{timestamp}.pdf")

    file = await bot.get_file(message.document.file_id)
    await file.download_to_drive(path)

    mark_agreement_signed(message.from_user.id)

    await message.reply(
        "✅ Agreement received!\n\n"
        f"🔗 Register on Naira Trader:\n{NAIRA_TRADER_LINK}\n\n"
        f"👥 Private Group:\n{PRIVATE_GROUP_LINK}"
    )

    await bot.send_message(
        ADMIN_CHAT_ID,
        f"📄 Agreement uploaded\nUser: @{message.from_user.username}\nFile: {path}"
    )

# ================== KORAPAY WEBHOOK ==================
async def korapay_webhook(request):
    body = await request.json()
    print("🔥 Webhook:", body)

    if body.get("event") != "charge.success":
        return web.Response(text="ignored")

    data = body["data"]
    reference = data.get("reference")
    amount = float(data.get("amount", 0))

    if amount < 20000:
        print("❌ Amount too low")
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
async def handle(request):
    return web.Response(text="MakeBankGuru Bot Running ✔️")

async def start_webserver():
    app = web.Application()
    app.add_routes([
        web.get("/", handle),
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
