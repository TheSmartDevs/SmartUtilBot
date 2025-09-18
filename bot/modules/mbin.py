# Copyright @ISmartCoder
# SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
# Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from bot import dp
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.buttons import SmartButtons
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.defend import SmartDefender
from config import UPDATE_CHANNEL_URL
from smartbindb import SmartBinDB
import pycountry
import os
import asyncio

smartdb = SmartBinDB()

async def get_bin_info(bin: str, bot: Bot, message: Message):
    try:
        result = await smartdb.get_bin_info(bin)
        if result.get("status") == "SUCCESS" and result.get("data") and isinstance(result["data"], list) and len(result["data"]) > 0:
            return result
        else:
            LOGGER.error(f"SmartBinDB returned invalid response for BIN: {bin} - {result}")
            await Smart_Notify(bot, "mbin", f"SmartBinDB invalid response: {result}", message)
            return None
    except Exception as e:
        LOGGER.error(f"Error fetching BIN info from SmartBinDB: {bin} - {str(e)}")
        await Smart_Notify(bot, "mbin", e, message)
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
    except:
        return "Unknown", ""

@dp.message(Command(commands=["mbin"], prefix=BotCommands))
@new_task
@SmartDefender
async def bin_handler(message: Message, bot: Bot):
    LOGGER.info(f"Received /mbin command from user: {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
    progress_message = None
    try:
        bins = []
        if message.reply_to_message and message.reply_to_message.document:
            file_path = f"bin_{message.chat.id}.txt"
            await bot.download(message.reply_to_message.document, destination=file_path)
            with open(file_path, 'r') as f:
                bins = [line.strip()[:6] for line in f.readlines() if line.strip() and len(line.strip()) >= 6 and line.strip()[:6].isdigit()]
            clean_download()
            LOGGER.info(f"BINs extracted from uploaded file by user: {message.from_user.id}")
        else:
            args = get_args(message)
            if not args:
                progress_message = await send_message(
                    chat_id=message.chat.id,
                    text="<b>Provide a valid BIN (6 digits) or reply to a text file containing BINs ❌</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.warning(f"No BIN provided by user: {message.from_user.id}")
                return
            bins = [arg[:6] for arg in args if len(arg) >= 6 and arg[:6].isdigit()]

        if not bins:
            progress_message = await send_message(
                chat_id=message.chat.id,
                text="<b>Provide valid BINs (6 digits) ❌</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.warning(f"No valid BINs provided by user: {message.from_user.id}")
            return

        if len(bins) > 20:
            progress_message = await send_message(
                chat_id=message.chat.id,
                text="<b>You can check up to 20 BINs at a time ❌</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.warning(f"User {message.from_user.id} tried to fetch more than 20 BINs")
            return

        invalid_bins = [bin for bin in bins if len(bin) != 6 or not bin.isdigit()]
        if invalid_bins:
            progress_message = await send_message(
                chat_id=message.chat.id,
                text=f"<b>Invalid BINs provided ❌</b> {' '.join(invalid_bins)}",
                parse_mode=ParseMode.HTML
            )
            LOGGER.warning(f"Invalid BIN formats from user: {message.from_user.id} - {invalid_bins}")
            return

        progress_message = await send_message(
            chat_id=message.chat.id,
            text="<b>Fetching BINs Info...✨</b>",
            parse_mode=ParseMode.HTML
        )

        async def fetch_bin_info(bin):
            bin_info = await get_bin_info(bin, bot, message)
            if bin_info:
                bank = bin_info["data"][0].get("issuer", "Unknown")
                card_type = bin_info["data"][0].get("type", "Unknown")
                card_scheme = bin_info["data"][0].get("brand", "Unknown")
                bank_text = bank.upper() if bank else "Unknown"
                country_code = bin_info["data"][0].get("country_code", "Unknown")
                country_name, flag_emoji = get_flag(country_code)
                return (
                    f"<b>• BIN:</b> {bin}\n"
                    f"<b>• INFO:</b> {card_scheme.upper()} - {card_type.upper()}\n"
                    f"<b>• BANK:</b> {bank_text}\n"
                    f"<b>• COUNTRY:</b> {country_name.upper()} {flag_emoji}\n\n"
                )
            else:
                return f"<b>• BIN:</b> {bin}\n<b>• INFO:</b> Not Found\n\n"

        tasks = [fetch_bin_info(bin) for bin in bins]
        results = await asyncio.gather(*tasks)
        response_text = (
            f"<b>🔍 BIN Details From Smart Database 📋</b>\n"
            f"<b>━━━━━━━━━━━━━━━━━━</b>\n"
            f"{' '.join(results)}"
            f"<b>━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>🔍 Smart Bin Checker → Activated ✅</b>"
        )

        buttons = SmartButtons()
        buttons.button(text="Join For Updates", url=UPDATE_CHANNEL_URL)
        await delete_messages(message.chat.id, progress_message.message_id)
        await send_message(
            chat_id=message.chat.id,
            text=response_text,
            parse_mode=ParseMode.HTML,
            reply_markup=buttons.build_menu(b_cols=1)
        )
        LOGGER.info(f"Successfully sent BIN details for {len(bins)} BINs to chat {message.chat.id}")

    except Exception as e:
        LOGGER.error(f"Error processing /mbin command in chat {message.chat.id}: {str(e)}")
        await Smart_Notify(bot, "mbin", e, message)
        if progress_message:
            try:
                await progress_message.edit_text(
                    text="<b>❌ Sorry Bro BIN API Error</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Edited progress message with BIN error in chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                await Smart_Notify(bot, "mbin", edit_e, message)
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
    finally:
        clean_download()