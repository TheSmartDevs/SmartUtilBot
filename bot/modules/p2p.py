# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
#  Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
import aiohttp
import asyncio
import json
import os
from aiogram import Bot
from aiogram.filters import Command, BaseFilter
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ParseMode
from bot import dp
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages
from bot.helpers.commands import BotCommands
from bot.helpers.buttons import SmartButtons
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.defend import SmartDefender
from config import A360APIBASEURL

url = f"{A360APIBASEURL}/p2p"

async def fetch_sellers(asset, fiat, trade_type, pay_type):
    params = {
        "asset": asset,
        "pay_type": pay_type,
        "trade_type": trade_type,
        "limit": 100
    }
    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params) as response:
            if response.status != 200:
                LOGGER.error(f"Error fetching data: {response.status}")
                raise Exception(f"API request failed with status {response.status}")
            data = await response.json()
            if not data.get("success", False):
                LOGGER.error(f"API returned success: false")
                raise Exception("API returned success: false")
            LOGGER.info(f"Successfully fetched {len(data['data'])} sellers for {asset} in {fiat}")
            return data['data']

def process_sellers_to_json(sellers, fiat):
    processed = []
    for seller in sellers:
        processed.append({
            "seller": seller.get("seller_name", "Unknown"),
            "price": f"{seller['price']} {fiat}",
            "available_usdt": f"{seller['available_amount']} USDT",
            "min_amount": f"{seller['min_order_amount']} {fiat}",
            "max_amount": f"{seller['max_order_amount']} {fiat}",
            "completion_rate": f"{seller['completion_rate']}%",
            "trade_method": ", ".join(seller['payment_methods']) if seller['payment_methods'] else "Unknown"
        })
    return processed

def save_to_json_file(data, filename, bot=None, message=None):
    os.makedirs('downloads', exist_ok=True)
    path = os.path.join('downloads', filename)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)
    LOGGER.info(f"Data saved to {path}")
    asyncio.create_task(delete_file_after_delay(10*60))

def load_from_json_file(filename, bot=None, message=None):
    path = os.path.join('downloads', filename)
    if not os.path.exists(path):
        LOGGER.error(f"File not found: {path}")
        raise Exception("File not found")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

async def delete_file_after_delay(delay):
    await asyncio.sleep(delay)
    clean_download()
    LOGGER.info("Downloads folder cleaned after delay")

def generate_message(sellers, page, fiat):
    start = (page - 1) * 10
    end = start + 10
    selected_sellers = sellers[start:end]
    message = f"<b>💱 Latest P2P USDT Trades for {fiat} 👇</b>\n\n"
    for i, seller in enumerate(selected_sellers, start=start + 1):
        message += (
            f"<b>{i}. Name:</b> {seller['seller']}\n"
            f"<b>Price:</b> {seller['price']}\n"
            f"<b>Payment Method:</b> {seller['trade_method']}\n"
            f"<b>Crypto Amount:</b> {seller['available_usdt']}\n"
            f"<b>Limit:</b> {seller['min_amount']} - {seller['max_amount']}\n\n"
        )
    return message

class P2PCallbackFilter(BaseFilter):
    async def __call__(self, callback_query: CallbackQuery):
        return callback_query.data.startswith(("nextone_", "prevone_"))

@dp.message(Command(commands=["p2p"], prefix=BotCommands))
@new_task
@SmartDefender
async def p2p_handler(message: Message, bot: Bot):
    try:
        command = message.text.split()
        if len(command) != 2:
            await send_message(
                chat_id=message.chat.id,
                text="<b>Please provide a currency. e.g. /p2p BDT or /p2p SAR</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.warning(f"Invalid command format: {message.text} in chat {message.chat.id}")
            return
        fiat = command[1].upper()
        asset = "USDT"
        trade_type = "SELL"
        pay_type = fiat
        filename = f"p2p_{asset}_{fiat}.json"
        LOGGER.info(f"Fetching P2P trades for {asset} in {fiat} using {pay_type}")
        progress_message = await send_message(
            chat_id=message.chat.id,
            text="<b>🔄 Fetching All P2P Trades</b>",
            parse_mode=ParseMode.HTML
        )
        sellers = await fetch_sellers(asset, fiat, trade_type, pay_type)
        if not sellers:
            await delete_messages(message.chat.id, [progress_message.message_id])
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ No sellers found or API error occurred</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.warning(f"No sellers found for {asset} in {fiat} in chat {message.chat.id}")
            return
        processed_sellers = process_sellers_to_json(sellers, fiat)
        save_to_json_file(processed_sellers, filename, bot=bot, message=message)
        message_text = generate_message(processed_sellers, 1, fiat)
        buttons = SmartButtons()
        buttons.button(text="➡️ Next", callback_data=f"nextone_1_{filename}")
        await delete_messages(message.chat.id, [progress_message.message_id])
        await send_message(
            chat_id=message.chat.id,
            text=message_text,
            parse_mode=ParseMode.HTML,
            reply_markup=buttons.build_menu(b_cols=1)
        )
        LOGGER.info(f"Sent P2P trades for {asset} in {fiat} to chat {message.chat.id}")
    except Exception as e:
        await delete_messages(message.chat.id, [progress_message.message_id])
        await send_message(
            chat_id=message.chat.id,
            text="<b>Sorry, an error occurred while fetching P2P data ❌</b>",
            parse_mode=ParseMode.HTML
        )
        LOGGER.error(f"Error processing /p2p in chat {message.chat.id}: {e}")
        await Smart_Notify(bot, "/p2p", e, message)

@dp.callback_query(P2PCallbackFilter())
@new_task
@SmartDefender
async def p2p_pagination(callback_query: CallbackQuery, bot: Bot):
    try:
        action, current_page, filename = callback_query.data.split('_', 2)
        current_page = int(current_page)
        sellers = load_from_json_file(filename, bot=bot, message=callback_query.message)
        fiat = filename.split('_')[2].split('.')[0]
        new_page = current_page + 1 if action == "nextone" else current_page - 1
        if new_page < 1 or (new_page - 1) * 10 >= len(sellers):
            await callback_query.answer("❌ Data Expired. Please Request Again To Get Latest Database")
            LOGGER.info(f"Data expired for page {new_page} in chat {callback_query.message.chat.id}")
            return
        message_text = generate_message(sellers, new_page, fiat)
        buttons = SmartButtons()
        if new_page > 1:
            buttons.button(text="⬅️ Previous", callback_data=f"prevone_{new_page}_{filename}")
        if (new_page * 10) < len(sellers):
            buttons.button(text="➡️ Next", callback_data=f"nextone_{new_page}_{filename}")
        await callback_query.message.edit_text(
            text=message_text,
            parse_mode=ParseMode.HTML,
            reply_markup=buttons.build_menu(b_cols=2)
        )
        await callback_query.answer()
        LOGGER.info(f"Updated to page {new_page} for {filename} in chat {callback_query.message.chat.id}")
    except Exception as e:
        await callback_query.message.edit_text(
            text="<b>Sorry, an error occurred while fetching data ❌</b>",
            parse_mode=ParseMode.HTML
        )
        LOGGER.error(f"Error in pagination for {callback_query.data} in chat {callback_query.message.chat.id}: {e}")
        await Smart_Notify(bot, "/p2p pagination", e, callback_query.message)