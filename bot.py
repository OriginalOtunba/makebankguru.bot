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
    headers = {
        "Authorization": f"Bearer {KORA_SECRET_KEY}",
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(
            VERIFY_ENDPOINT.format(reference=reference),
            headers=headers
        ) as resp:
            data = await resp.json()
            print("🔎 Korapay verify response:", data)

            if not data.get("status"):
                return False

            payment = data.get("data", {})
            status = payment.get("status")
            currency = payment.get("currency")
            amount = payment.get("amount") or payment.get("amount_paid")

            if (
                status == "success"
                and currency == "NGN"
                and amount
                and float(amount) >= 20000
            ):
                return True

    return False


# ================== TELEGRAM HANDLERS ==================
async def start_cmd(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="Proceed to Confirmation 🔐", callback_data="confirm")
    await message.answer(
        "👋 *Welcome to MakeBankGuru!*\n\n"
        "This bot confirms your payment and handles your onboarding.",
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )

async def confirm_user(callback: types.CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="🔗 Register on Naira Trader", url=NAIRA_TRADER_LINK)
    await callback.message.edit_text(
        "Step 1: Register via our affiliate link below.\n\nThen proceed to Step 2 — payment confirmation.",
        parse_mode="Markdown",
        reply_markup=builder.as_markup()
    )
    await callback.message.answer(
        f"💵 Step 2: Pay ₦20,000 here:\n"
        f"[Korapay Payment Link]({KORAPAY_PAYMENT_LINK})\n\n"
        "After payment, you'll receive a *reference code*. Send it using:\n"
        "`/verify REF12345`",
        parse_mode="Markdown"
    )

async def verify_cmd(message: types.Message):
    if is_verified(message.from_user.id):
        if has_accepted_agreement(message.from_user.id):
            await message.reply("You are already fully verified ✔️")
            return
        else:
            await message.reply("Payment verified ✔️\nPlease upload your signed agreement PDF.")
            return

    # Extract reference
    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.reply("Send reference like: `/verify REF12345`", parse_mode="Markdown")
        return

    reference = parts[1]
    await message.reply("🔍 Checking payment status...")

    ok = await verify_payment(reference)
    if ok:
        add_user(telegram_id, username, reference)
        add_user(message.from_user.id, message.from_user.username or "N/A", reference)
        await message.reply(
            f"🎉 Payment confirmed!\n\nUpload your signed agreement PDF:\n"
            f"[Agreement PDF]({AGREEMENT_LINK})",
            parse_mode="Markdown"
        )
    else:
        await message.reply("❌ Payment not found or pending. Try again shortly.")

async def receive_signed_pdf(message: types.Message):
    if not is_verified(message.from_user.id):
        await message.reply("You must verify your payment first.")
        return

    if not message.document.file_name.lower().endswith(".pdf"):
        await message.reply("❌ Only PDF files are allowed.")
        return

    timestamp = int(datetime.datetime.now().timestamp())
    save_path = os.path.join(
        SIGNED_DIR,
        f"{message.from_user.id}_{timestamp}.pdf"
    )

    file = await bot.get_file(message.document.file_id)
    await file.download_to_drive(save_path)

    # ✅ THIS LINE WAS MIS-INDENTED BEFORE
    mark_agreement_accepted(message.from_user.id)

    await message.reply(
        "Agreement received ✔️\nYou now have access:\n"
        f"🔗 {NAIRA_TRADER_LINK}\n"
        f"👥 Private Group: {PRIVATE_GROUP_LINK}"
    )

    await bot.send_message(
        ADMIN_CHAT_ID,
        f"📄 New Agreement Uploaded\n"
        f"User: @{message.from_user.username}\n"
        f"File: {save_path}"
    )


# ================== KORAPAY WEBHOOK ==================
async def korapay_webhook(request):
    try:
        body = await request.json()
        print("🔥 Incoming webhook:", body)

        if body.get("event") != "charge.success":
            return web.Response(text="Ignored")

        data = body.get("data", {})
        reference = data.get("reference")
        amount = data.get("amount")
        currency = data.get("currency")

        if currency == "NGN" and float(amount) >= 20000:
            # TODO: map reference → telegram user
            print("✔️ Payment confirmed via webhook:", reference)

        return web.Response(text="OK")

    except Exception as e:
        print("Webhook error:", e)
        return web.Response(status=400, text="Webhook Error")


# ================== RENDER WEB SERVER ==================
async def handle(request):
    return web.Response(text="MakeBankGuru Bot Running ✔️")

async def start_webserver():
    app = web.Application()
    app.add_routes([
        web.get('/', handle),
        web.post('/korapay-webhook', korapay_webhook)
    ])

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"🌍 Webserver running on {port}")

# ================== MAIN ==================
async def main():
    await start_webserver()
    print("🤖 Telegram bot running...")

    dp.message.register(start_cmd, Command("start"))
    dp.callback_query.register(confirm_user, F.data == "confirm")
    dp.message.register(verify_cmd, Command("verify"))
    dp.message.register(receive_signed_pdf, F.document & ~F.text)


    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())









