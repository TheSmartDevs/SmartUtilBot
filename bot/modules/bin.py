from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from bot import dp
from bot.helpers.utils import new_task
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.defend import SmartDefender
from bot.helpers.bindb import smartdb
import pycountry

async def get_bin_info(bin: str, bot: Bot, message: Message):
    try:
        result = await smartdb.get_bin_info(bin)
        if result.get("status") == "SUCCESS" and result.get("data") and isinstance(result["data"], list) and len(result["data"]) > 0:
            return result
        else:
            LOGGER.error(f"SmartBinDB returned invalid response: {result}")
            await Smart_Notify(bot, "bin", f"SmartBinDB invalid response: {result}", message)
            return None
    except Exception as e:
        LOGGER.error(f"Error fetching BIN info from SmartBinDB: {str(e)}")
        await Smart_Notify(bot, "bin", e, message)
        return None

def get_flag(country_code: str):
    try:
        if not country_code or len(country_code) < 2:
            return "Unknown", ""
        country_code = country_code.upper()
        if country_code in ['US1', 'US2']:
            country_code = 'US'
        country = pycountry.countries.get(alpha_2=country_code)
        if not country:
            return "Unknown", ""
        country_name = country.name
        flag_emoji = chr(0x1F1E6 + ord(country_code[0]) - ord('A')) + chr(0x1F1E6 + ord(country_code[1]) - ord('A'))
        return country_name, flag_emoji
    except Exception:
        return "Unknown", ""

@dp.message(Command(commands=["bin"], prefix=BotCommands))
@new_task
@SmartDefender
async def bin_handler(message: Message, bot: Bot):
    LOGGER.info(f"Received command: '{message.text}' from user {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
    progress_message = None
    try:
        args = get_args(message)
        if not args:
            progress_message = await send_message(
                chat_id=message.chat.id,
                text="<b>Provide a valid BIN ❌</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"No BIN provided in chat {message.chat.id}")
            return
        progress_message = await send_message(
            chat_id=message.chat.id,
            text="<b>Fetching Bin Details...</b>",
            parse_mode=ParseMode.HTML
        )
        bin = args[0][:6]
        bin_info = await get_bin_info(bin, bot, message)
        if not bin_info:
            await progress_message.edit_text(
                text="<b>Invalid BIN provided ❌</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Invalid BIN {bin} in chat {message.chat.id}")
            return
        bank = bin_info["data"][0].get("issuer", "Unknown")
        card_type = bin_info["data"][0].get("type", "Unknown")
        card_scheme = bin_info["data"][0].get("brand", "Unknown")
        bank_text = bank.upper() if bank else "Unknown"
        country_code = bin_info["data"][0].get("country_code", "")
        country_name, flag_emoji = get_flag(country_code)
        bin_info_text = (
            f"<b>🔍 BIN Details From Smart Database 📋</b>\n"
            f"<b>━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>• BIN:</b> {bin}\n"
            f"<b>• INFO:</b> {card_scheme.upper()} - {card_type.upper()}\n"
            f"<b>• BANK:</b> {bank_text}\n"
            f"<b>• COUNTRY:</b> {country_name.upper()} {flag_emoji}\n"
            f"<b>━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>🔍 Smart Bin Checker → Activated ✅</b>"
        )
        await progress_message.edit_text(
            text=bin_info_text,
            parse_mode=ParseMode.HTML
        )
        LOGGER.info(f"Successfully sent BIN details for {bin} to chat {message.chat.id}")
    except Exception as e:
        LOGGER.error(f"Error processing BIN command in chat {message.chat.id}: {str(e)}")
        await Smart_Notify(bot, "bin", e, message)
        if progress_message:
            try:
                await progress_message.edit_text(
                    text="<b>❌ Sorry Bro BIN API Error</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Edited progress message with BIN error in chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                await Smart_Notify(bot, "bin", edit_e, message)
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Sorry Bro BIN API Error</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Sent BIN error message to chat {message.chat.id}")
        else:
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Sorry Bro BIN API Error</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Sent BIN error message to chat {message.chat.id}")