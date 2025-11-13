import os
import asyncio
import aiohttp
import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
from database import init_db, add_user, is_verified

# Load .env variables
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
KORA_SECRET_KEY = os.getenv("KORA_SECRET_KEY")
NAIRA_TRADER_LINK = os.getenv("NAIRA_TRADER_LINK")
PRIVATE_GROUP_LINK = os.getenv("PRIVATE_GROUP_LINK")
ACCOUNT_SETUP_FORM = os.getenv("ACCOUNT_SETUP_FORM")
KORAPAY_PAYMENT_LINK = os.getenv("KORAPAY_PAYMENT_LINK")

VERIFY_ENDPOINT = "https://api.korapay.com/merchant/api/v1/charges/{reference}"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Initialize database
init_db()

# === Payment Verification ===
async def verify_payment(reference: str) -> bool:
    headers = {"Authorization": f"Bearer {KORA_SECRET_KEY}"}
    async with aiohttp.ClientSession() as session:
        async with session.get(VERIFY_ENDPOINT.format(reference=reference), headers=headers) as resp:
            data = await resp.json()
            if data.get("status") and data["data"].get("status") == "success":
                if data["data"].get("amount_paid") == 20000 and data["data"].get("currency") == "NGN":
                    return True
    return False

# === /start ===
@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="Proceed to Confirmation 🔐", callback_data="confirm")
    await message.answer(
        "👋 *Welcome to MakeBankGuru!*\n\n"
        "This bot confirms your payment and gives you access to our premium flipping service.",
        parse
