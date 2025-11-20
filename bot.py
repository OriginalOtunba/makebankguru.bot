import os
import asyncio
import aiohttp
import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
from database import init_db, add_user, is_verified, mark_agreement_accepted, has_accepted_agreement
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

VERIFY_ENDPOINT = "https://api.korapay.com/merchant/api/v1/charges/{reference}"
SIGNED_DIR = "signed_agreements"

# ================== BOT SETUP ==================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
init_db()
os.makedirs(SIGNED_DIR, exist_ok=True)

# ================== PAYMENT VERIFICATION ==================
async def verify_payment(reference: str) -> bool:
    headers = {"Authorization": f"Bearer {KORA_SECRET_KEY}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(VERIFY_ENDPOINT.format(reference=reference), headers=headers) as resp:
            data = await resp.json()
            if data.get("status") and data["data"].get("status") == "success":
                if data["data"].get("amount_paid") == 20000 and data["data"].get("currency") == "NGN":
                    return True
    return False

# ================== HANDLERS ==================
async def start_cmd(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="Proceed to Confirmation 🔐", callback_data="confirm")
    await message.answer(
        "👋 *Welcome to MakeBankGuru!*\n\n"
        "This bot confirms your payment and guides you through the agreement to access our premium support service.",
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )

async def confirm_user(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔗 Register on Naira Trader", url=NAIRA_TRADER_LINK)
    await callback.message.edit_text(
        "✅ Step 1: Register via our affiliate link below.\n\nOnce done, proceed to Step 2 — payment confirmation.",
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )
    await callback.message.answer(
        f"💵 Step 2: Pay ₦20,000 setup fee here:\n\n"
        f"👉 [Korapay Payment Link]({KORAPAY_PAYMENT_LINK})\n\n"
        "After payment, you’ll get a *payment reference code*. Send it below in this format:\n"
        "`/verify REF12345`",
        parse_mode="Markdown"
    )

async def verify_cmd(message: types.Message):
    if is_verified(message.from_user.id):
        if has_accepted_agreement(message.from_user.id):
            await message.reply("✅ You’re already verified and agreement uploaded.")
            return
        else:
            await message.reply("✅ Payment verified. Please upload your signed agreement PDF to proceed.")
            return

    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.reply("⚠️ Please include your payment reference. Example: `/verify REF12345`", parse_mode="Markdown")
        return

    reference = parts[1]
    await message.reply("🔍 Checking payment status...")

    ok = await verify_payment(reference)
    if ok:
        add_user(message.from_user.id, message.from_user.username or "N/A", reference)
        await message.reply(
            f"🎉 Payment confirmed!\n\nPlease download, sign, and upload your service agreement PDF to this chat:\n🧾 [Service Agreement PDF]({AGREEMENT_LINK})",
            parse_mode="Markdown"
        )
    else:
        await message.reply("❌ Payment not found or pending. Try again shortly.")

async def receive_signed_pdf(message: types.Message):
    if not is_verified(message.from_user.id):
        await message.reply("⚠️ You must verify your payment first.")
        return

    if not message.document.file_name.lower().endswith(".pdf"):
        await message.reply("❌ Only PDF files are accepted.")
        return

    timestamp = int(datetime.datetime.now().timestamp())
    save_path = os.path.join(SIGNED_DIR, f"{message.from_user.id}_{timestamp}.pdf")
    file = await bot.get_file(message.document.file_id)
    await file.download_to_drive(save_path)

    mark_agreement_accepted(message.from_user.id)

    await message.reply(
        "✅ Signed agreement received successfully! You now have access:\n"
        f"🔗 Naira Trader Registration: {NAIRA_TRADER_LINK}\n"
        f"👥 Private Group: {PRIVATE_GROUP_LINK}"
    )

    await bot.send_message(
        ADMIN_CHAT_ID,
        f"📄 New signed agreement uploaded!\n"
        f"User: @{message.from_user.username} ({message.from_user.id})\n"
        f"File saved: {save_path}"
    )

# ================== DUMMY WEB SERVER (RENDER FREE PLAN) ==================
async def handle(request):
    return web.Response(text="🤖 MakeBankGuru Bot Running!")

async def start_webserver():
    app = web.Application()
    app.add_routes([web.get('/', handle)])
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🌐 Webserver running on port {port}")

    # self-ping to stay awake
    async def self_ping():
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    await session.get(f"http://localhost:{port}")
            except Exception as e:
                print("Ping error:", e)
            await asyncio.sleep(600)

    asyncio.create_task(self_ping())

# ================== RUN BOT + WEB SERVER ==================
async def main():
    await start_webserver()
    print("🤖 MakeBankGuru Verification Bot running...")

    # Register handlers explicitly (Aiogram v3)
    dp.message.register(start_cmd, Command("start"))
    dp.callback_query.register(confirm_user, F.data == "confirm")
    dp.message.register(verify_cmd, Command("verify"))
    dp.message.register(receive_signed_pdf, F.document)

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

