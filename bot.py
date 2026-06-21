import asyncio
import logging
import os
import random

import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from dotenv import load_dotenv

import cards_api
import economy
import inventory
import market
import trade
from db import init_db

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

dp = Dispatcher()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def format_seconds(seconds: int) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours} ساعت و {minutes} دقیقه"
    if minutes:
        return f"{minutes} دقیقه و {secs} ثانیه"
    return f"{secs} ثانیه"


async def ensure(message: Message):
    user = message.from_user
    await economy.ensure_user(user.id, user.username or user.full_name or str(user.id))


async def refund_pack(user_id: int):
    """Used if the card API fails after a pack has already been consumed."""
    async with aiosqlite.connect(economy.DB_NAME) as db:
        await db.execute(
            "UPDATE users SET packs = packs + 1 WHERE user_id=?", (user_id,)
        )
        await db.commit()


# ---------------------------------------------------------------------------
# Basic commands
# ---------------------------------------------------------------------------

@dp.message(Command("start"))
async def start_cmd(message: Message):
    await ensure(message)
    await message.answer(
        "به ربات کارت‌های پوکمون خوش اومدی! 🎴\n\n"
        "برای دیدن لیست دستورها /help رو بزن."
    )


@dp.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer(
        "📜 <b>دستورهای ربات</b>\n\n"
        "💰 /mony - دریافت امتیاز رایگان (هر ساعت یک‌بار)\n"
        "💳 /balance - مشاهده موجودی\n"
        "🛒 /shop - خرید پک با 30 امتیاز\n"
        "🎁 /open - باز کردن یک پک (8 کارت)\n"
        "🎒 /inv - مشاهده اینونتوری\n"
        "🏷️ /sell &lt;نام کارت&gt; &lt;قیمت&gt; - گذاشتن کارت در بازار\n"
        "🏪 /market - مشاهده بازار\n"
        "💸 /buy &lt;شماره آگهی&gt; - خرید کارت از بازار\n"
        "❌ /cancel &lt;شماره آگهی&gt; - لغو آگهی فروش\n"
        "🔁 /trade &lt;کارت من&gt; / &lt;کارت طرف&gt; - معامله (ریپلای روی پیام طرف مقابل)\n"
    )


@dp.message(Command("balance"))
async def balance_cmd(message: Message):
    await ensure(message)
    money = await economy.get_balance(message.from_user.id)
    packs = await economy.get_packs(message.from_user.id)
    await message.answer(f"💰 موجودی: {money} امتیاز\n📦 پک‌های باز نشده: {packs}")


# ---------------------------------------------------------------------------
# Economy: /mony, /shop, /open
# ---------------------------------------------------------------------------

@dp.message(Command("mony"))
async def mony_cmd(message: Message):
    await ensure(message)
    user_id = message.from_user.id

    can_claim, remain = await economy.can_claim_mony(user_id)
    if not can_claim:
        await message.answer(f"⏳ هنوز زوده! {format_seconds(remain)} دیگه دوباره امتحان کن.")
        return

    amount = random.randint(economy.MONY_MIN, economy.MONY_MAX)

    await economy.add_money(user_id, amount)
    await economy.update_mony_time(user_id)

    await message.answer(f"🎉 {amount} امتیاز گرفتی!")


@dp.message(Command("shop"))
async def shop_cmd(message: Message):
    await ensure(message)
    user_id = message.from_user.id

    success = await economy.buy_pack(user_id)
    if not success:
        await message.answer(
            f"❌ امتیاز کافی نداری. هر پک {economy.PACK_PRICE} امتیاز قیمت داره."
        )
        return

    packs = await economy.get_packs(user_id)
    await message.answer(f"✅ یک پک خریدی! الان {packs} پک داری.\nبرای باز کردن /open رو بزن.")


@dp.message(Command("open"))
async def open_cmd(message: Message):
    await ensure(message)
    user_id = message.from_user.id

    consumed = await economy.consume_pack(user_id)
    if not consumed:
        await message.answer("❌ پکی نداری. اول با /shop یک پک بخر.")
        return

    waiting = await message.answer("🎴 در حال باز کردن پک...")

    cards = await cards_api.get_random_cards_detailed(8)
    if not cards:
        await refund_pack(user_id)
        await waiting.edit_text(
            "⚠️ مشکلی در دریافت کارت‌ها از سرور پیش اومد. پکت برگردونده شد، دوباره امتحان کن."
        )
        return

    lines = ["🎉 <b>کارت‌های جدید تو:</b>\n"]
    for card in cards:
        name = card.get("name", "Unknown")
        rarity = card.get("rarity", "Unknown")
        card_id = card.get("id", "")
        await inventory.add_card(user_id, card_id, name, rarity)
        lines.append(f"• {name} ({rarity})")

    await waiting.edit_text("\n".join(lines))


# ---------------------------------------------------------------------------
# Inventory: /inv
# ---------------------------------------------------------------------------

@dp.message(Command("inv"))
async def inv_cmd(message: Message):
    await ensure(message)
    items = await inventory.get_inventory(message.from_user.id)

    if not items:
        await message.answer("🎒 اینونتوری‌ت خالیه. با /shop و /open کارت جمع کن.")
        return

    lines = ["🎒 <b>اینونتوری تو:</b>\n"]
    for name, count in items:
        lines.append(f"• {name} × {count}")

    await message.answer("\n".join(lines))


# ---------------------------------------------------------------------------
# Market: /sell, /market, /buy, /cancel
# ---------------------------------------------------------------------------

@dp.message(Command("sell"))
async def sell_cmd(message: Message, command: CommandObject):
    await ensure(message)
    user_id = message.from_user.id

    if not command.args:
        await message.answer("استفاده: /sell <نام کارت> <قیمت>\nمثال: /sell Pikachu 50")
        return

    parts = command.args.rsplit(" ", 1)
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("استفاده: /sell <نام کارت> <قیمت>\nمثال: /sell Pikachu 50")
        return

    card_name, price_str = parts
    card_name = card_name.strip()
    price = int(price_str)

    if price <= 0:
        await message.answer("❌ قیمت باید بزرگ‌تر از صفر باشه.")
        return

    success = await market.list_card_for_sale(user_id, card_name, price)
    if not success:
        await message.answer(f"❌ کارت «{card_name}» رو در اینونتوریت پیدا نکردم.")
        return

    await message.answer(f"✅ «{card_name}» با قیمت {price} امتیاز در بازار گذاشته شد.")


@dp.message(Command("market"))
async def market_cmd(message: Message):
    listings = await market.get_market_cards()

    if not listings:
        await message.answer("🏪 بازار الان خالیه.")
        return

    lines = ["🏪 <b>بازار کارت‌ها:</b>\n"]
    for sale_id, seller_id, card_name, price in listings[:30]:
        lines.append(f"#{sale_id} • {card_name} — {price} امتیاز")

    lines.append("\nبرای خرید: /buy <شماره آگهی>")
    await message.answer("\n".join(lines))


@dp.message(Command("buy"))
async def buy_cmd(message: Message, command: CommandObject):
    await ensure(message)
    user_id = message.from_user.id

    if not command.args or not command.args.strip().isdigit():
        await message.answer("استفاده: /buy <شماره آگهی>\nبرای دیدن شماره‌ها /market رو بزن.")
        return

    sale_id = int(command.args.strip())
    success = await market.buy_card(user_id, sale_id)

    if not success:
        await message.answer("❌ این آگهی پیدا نشد یا امتیازت کافی نیست.")
        return

    await message.answer("✅ کارت خریداری شد! می‌تونی توی /inv ببینیش.")


@dp.message(Command("cancel"))
async def cancel_cmd(message: Message, command: CommandObject):
    await ensure(message)
    user_id = message.from_user.id

    if not command.args or not command.args.strip().isdigit():
        await message.answer("استفاده: /cancel <شماره آگهی>")
        return

    sale_id = int(command.args.strip())
    success = await market.cancel_sale(user_id, sale_id)

    if not success:
        await message.answer("❌ این آگهی مال تو نیست یا قبلاً بسته شده.")
        return

    await message.answer("✅ آگهی لغو شد و کارت به اینونتوریت برگشت.")


# ---------------------------------------------------------------------------
# Trade: /trade (reply to the other user's message), accept/reject buttons
# ---------------------------------------------------------------------------

@dp.message(Command("trade"))
async def trade_cmd(message: Message, command: CommandObject):
    await ensure(message)

    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.answer(
            "برای معامله، روی پیام طرف مقابل ریپلای کن و بنویس:\n"
            "/trade <کارت من> / <کارت طرف>\nمثال: /trade Pikachu / Charmander"
        )
        return

    target_user = message.reply_to_message.from_user
    if not command.args or "/" not in command.args:
        await message.answer("فرمت درست: /trade <کارت من> / <کارت طرف>\nمثال: /trade Pikachu / Charmander")
        return

    if target_user.id == message.from_user.id:
        await message.answer("❌ نمی‌تونی با خودت معامله کنی.")
        return

    my_card, their_card = [p.strip() for p in command.args.split("/", 1)]
    if not my_card or not their_card:
        await message.answer("فرمت درست: /trade <کارت من> / <کارت طرف>\nمثال: /trade Pikachu / Charmander")
        return

    await economy.ensure_user(target_user.id, target_user.username or target_user.full_name)

    trade_id = await trade.create_trade(message.from_user.id, target_user.id, my_card, their_card)
    if trade_id is None:
        await message.answer(f"❌ کارت «{my_card}» رو در اینونتوریت پیدا نکردم.")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ قبول", callback_data=f"trade_accept:{trade_id}"),
        InlineKeyboardButton(text="❌ رد", callback_data=f"trade_reject:{trade_id}"),
    ]])

    await message.answer(
        f"🔁 پیشنهاد معامله از طرف {message.from_user.full_name}:\n"
        f"می‌ده: {my_card}\n"
        f"می‌خواد: {their_card}\n\n"
        f"{target_user.full_name} باید تایید کنه 👇",
        reply_markup=keyboard,
    )


@dp.callback_query(F.data.startswith("trade_accept:"))
async def trade_accept_cb(callback: CallbackQuery):
    trade_id = int(callback.data.split(":")[1])
    trade_row = await trade.get_trade(trade_id)

    if not trade_row:
        await callback.answer("این معامله دیگه وجود نداره.", show_alert=True)
        return

    user2 = trade_row[2]
    if callback.from_user.id != user2:
        await callback.answer("فقط طرف مقابل می‌تونه این معامله رو قبول کنه.", show_alert=True)
        return

    success = await trade.accept_trade(trade_id)
    if not success:
        await callback.answer("معامله ناموفق بود (شاید کارت‌ها دیگه موجود نیستن).", show_alert=True)
        if callback.message:
            await callback.message.edit_text(callback.message.text + "\n\n❌ معامله ناموفق بود.")
        return

    await callback.answer("معامله انجام شد ✅")
    if callback.message:
        await callback.message.edit_text(callback.message.text + "\n\n✅ معامله با موفقیت انجام شد.")


@dp.callback_query(F.data.startswith("trade_reject:"))
async def trade_reject_cb(callback: CallbackQuery):
    trade_id = int(callback.data.split(":")[1])
    trade_row = await trade.get_trade(trade_id)

    if not trade_row:
        await callback.answer("این معامله دیگه وجود نداره.", show_alert=True)
        return

    user2 = trade_row[2]
    if callback.from_user.id != user2:
        await callback.answer("فقط طرف مقابل می‌تونه این معامله رو رد کنه.", show_alert=True)
        return

    await trade.reject_trade(trade_id)
    await callback.answer("معامله رد شد.")
    if callback.message:
        await callback.message.edit_text(callback.message.text + "\n\n❌ معامله رد شد.")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN در متغیرهای محیطی تنظیم نشده (.env را بررسی کن).")

    await init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
