# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
#  Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
import aiohttp
import asyncio
from aiogram import Bot
from aiogram.filters import Command, BaseFilter
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ParseMode
from bot import dp
from bot.helpers.utils import new_task
from bot.helpers.botutils import send_message, delete_messages
from bot.helpers.commands import BotCommands
from bot.helpers.buttons import SmartButtons
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.defend import SmartDefender
from config import A360APIBASEURL
BASE_URL = f"{A360APIBASEURL}/binance/24h"
async def fetch_crypto_data():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(BASE_URL) as response:
                response.raise_for_status()
                data = await response.json()
                if not data.get("success", False):
                    LOGGER.error("API returned success: false")
                    raise Exception("API returned success: false")
                LOGGER.info("Successfully fetched crypto data from A360 API")
                return data['data']
    except Exception as e:
        LOGGER.error(f"Error fetching crypto data: {e}")
        raise Exception("Unable to fetch data from A360 API")
def get_top_gainers(data, top_n=5):
    return sorted(data, key=lambda x: float(x['priceChangePercent']), reverse=True)[:top_n]
def get_top_losers(data, top_n=5):
    return sorted(data, key=lambda x: float(x['priceChangePercent']))[:top_n]
def format_crypto_info(data, start_index=0):
    result = ""
    for idx, item in enumerate(data, start=start_index + 1):
        result += (
            f"{idx}. Symbol: {item['symbol']}\n"
            f" Change: {item['priceChangePercent']}%\n"
            f" Last Price: {item['lastPrice']}\n"
            f" 24h High: {item['highPrice']}\n"
            f" 24h Low: {item['lowPrice']}\n"
            f" 24h Volume: {item['volume']}\n"
            f" 24h Quote Volume: {item['quoteVolume']}\n\n"
        )
    return result
class CryptoCallbackFilter(BaseFilter):
    async def __call__(self, callback_query: CallbackQuery):
        return callback_query.data.startswith(("gainers_", "losers_"))
@dp.message(Command(commands=["gainers", "losers"], prefix=BotCommands))
@new_task
@SmartDefender
async def crypto_handle_command(message: Message, bot: Bot):
    command_text = message.text.split()[0]
    command = None
    for prefix in BotCommands:
        if command_text.startswith(prefix):
            command = command_text[len(prefix):].lower()
            break
    if not command:
        command = command_text.lower()
    progress_message = await send_message(
        chat_id=message.chat.id,
        text=f"<b>Fetching Top ⚡️ {command}...</b>",
        parse_mode=ParseMode.HTML
    )
    try:
        data = await fetch_crypto_data()
        top_n = 5
        if command == "gainers":
            top_cryptos = get_top_gainers(data, top_n)
            title = "Gainers"
        else:
            top_cryptos = get_top_losers(data, top_n)
            title = "Losers"
        formatted_info = format_crypto_info(top_cryptos)
        response_message = f"<b>List Of Top {title}:</b>\n\n{formatted_info}"
        buttons = SmartButtons()
        buttons.button(text="➡️ Next", callback_data=f"{command}_1")
        await delete_messages(message.chat.id, [progress_message.message_id])
        await send_message(
            chat_id=message.chat.id,
            text=response_message,
            parse_mode=ParseMode.HTML,
            reply_markup=buttons.build_menu(b_cols=1)
        )
        LOGGER.info(f"Sent top {title.lower()} to chat {message.chat.id}")
    except Exception as e:
        await delete_messages(message.chat.id, [progress_message.message_id])
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Error: Unable to fetch data from A360 API</b>",
            parse_mode=ParseMode.HTML
        )
        LOGGER.error(f"Error processing /{command}: {e}")
        await Smart_Notify(bot, f"/{command}", e, message)
@dp.callback_query(CryptoCallbackFilter())
@new_task
@SmartDefender
async def crypto_handle_pagination(callback_query: CallbackQuery, bot: Bot):
    command, page = callback_query.data.split('_')
    page = int(page)
    next_page = page + 1
    prev_page = page - 1
    try:
        data = await fetch_crypto_data()
        top_n = 5
        if command == "gainers":
            top_cryptos = get_top_gainers(data, top_n * next_page)[page*top_n:(page+1)*top_n]
            title = "Gainers"
        else:
            top_cryptos = get_top_losers(data, top_n * next_page)[page*top_n:(page+1)*top_n]
            title = "Losers"
        if not top_cryptos:
            await callback_query.answer(f"No more {title.lower()} to display", show_alert=True)
            LOGGER.info(f"No more {title.lower()} for page {page} in chat {callback_query.message.chat.id}")
            return
        formatted_info = format_crypto_info(top_cryptos, start_index=page*top_n)
        response_message = f"<b>List Of Top {title} (Page {page + 1}):</b>\n\n{formatted_info}"
        buttons = SmartButtons()
        if prev_page >= 0:
            buttons.button(text="⬅️ Previous", callback_data=f"{command}_{prev_page}")
        if len(top_cryptos) == top_n:
            buttons.button(text="➡️ Next", callback_data=f"{command}_{next_page}")
        await callback_query.message.edit_text(
            text=response_message,
            parse_mode=ParseMode.HTML,
            reply_markup=buttons.build_menu(b_cols=2)
        )
        await callback_query.answer()
        LOGGER.info(f"Updated pagination for {command} (page {page + 1}) in chat {callback_query.message.chat.id}")
    except Exception as e:
        await callback_query.answer("❌ Error fetching data", show_alert=True)
        LOGGER.error(f"Error in pagination for {command} (page {page + 1}): {e}")
        await Smart_Notify(bot, f"/{command} pagination", e, callback_query.message)