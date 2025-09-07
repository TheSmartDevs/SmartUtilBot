# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
#  Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
import re
import os
import time
import asyncio
from aiogram import Bot
from aiogram.filters import Command, BaseFilter
from aiogram.types import Message, FSInputFile
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from bot import dp
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages
from bot.helpers.commands import BotCommands
from bot.helpers.buttons import SmartButtons
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.defend import SmartDefender
from config import UPDATE_CHANNEL_URL, MAX_TXT_SIZE

async def filter_valid_cc(content):
    valid_cc_patterns = [
        re.compile(r'^(\d{16}\|\d{2}\|\d{2}\|\d{3})\|.*$'),
        re.compile(r'^(\d{16}\|\d{2}\|\d{2}\|\d{4})\|.*$'),
        re.compile(r'^(\d{16}\|\d{2}\|\d{4}\|\d{3})\|.*$'),
        re.compile(r'^(\d{16}\|\d{2}\|\d{4}\|\d{4})\|.*$'),
        re.compile(r'^(\d{13}\|\d{2}\|\d{2}\|\d{3})\|.*$'),
        re.compile(r'^(\d{13}\|\d{2}\|\d{2}\|\d{4})\|.*$'),
        re.compile(r'^(\d{13}\|\d{2}\|\d{4}\|\d{3})\|.*$'),
        re.compile(r'^(\d{13}\|\d{2}\|\d{4}\|\d{4})\|.*$'),
        re.compile(r'^(\d{19}\|\d{2}\|\d{2}\|\d{3})\|.*$'),
        re.compile(r'^(\d{19}\|\d{2}\|\d{2}\|\d{4})\|.*$'),
        re.compile(r'^(\d{19}\|\d{2}\|\d{4}\|\d{3})\|.*$'),
        re.compile(r'^(\d{19}\|\d{2}\|\d{4}\|\d{4})\|.*$'),
        re.compile(r'^(\d{16}\|\d{2}\|\d{2,4}\|\d{3,4})$'),
        re.compile(r'(\d{15,16})\|(\d{1,2})/(\d{2,4})\|(\d{3,4})\|'),
        re.compile(r'(\d{15,16})\s*(\d{2})\s*(\d{2,4})\s*(\d{3,4})'),
        re.compile(r'(\d{15,16})\|(\d{4})(\d{2})\|(\d{3,4})\|'),
        re.compile(r'(\d{15,16})\|(\d{3,4})\|(\d{4})(\d{2})\|'),
        re.compile(r'(\d{15,16})\|(\d{3,4})\|(\d{2})\|(\d{2})\|'),
        re.compile(r'(\d{15,16})\|(\d{2})\|(\d{2})\|(\d{3})\|'),
        re.compile(r'(\d{15,16})\s*(\d{1,2})\s*(\d{2})\s*(\d{3,4})'),
        re.compile(r'(\d{15,16})\|(\d{2})\|(\d{2})\|(\d{3,4})\|'),
        re.compile(r'(\d{15,16})\s*(\d{3,4})\s*(\d{1,2})\s*(\d{2,4})'),
        re.compile(r'(\d{13,19})\s+(\d{2}/\d{2,4})\s+(\d{3,4})')
    ]
    valid_ccs = []
    for line in content:
        stripped_line = line.strip()
        matched = False
        for pattern in valid_cc_patterns:
            match = pattern.match(stripped_line)
            if match:
                if len(match.groups()) >= 4:
                    cc = match.group(1)
                    month = match.group(2)
                    year = match.group(3)
                    cvv = match.group(4)
                    if "/" in month or "/" in year:
                        month = month.replace("/", "|")
                        year = year.replace("/", "|")
                    if len(year) == 2:
                        year = "20" + year
                    cc_details = f"{cc}|{month}|{year}|{cvv}"
                    valid_ccs.append(cc_details)
                    matched = True
                    break
                elif len(match.groups()) == 3:
                    cc = match.group(1)
                    exp_date = match.group(2)
                    cvv = match.group(3)
                    exp_date = exp_date.replace("/", "|")
                    if len(exp_date.split("|")[1]) == 2:
                        exp_date = exp_date.replace("|", "|20", 1)
                    cc_details = f"{cc}|{exp_date}|{cvv}"
                    valid_ccs.append(cc_details)
                    matched = True
                    break
                elif len(match.groups()) == 1:
                    cc_details = match.group(1)
                    parts = cc_details.split("|")
                    if len(parts) >= 3 and len(parts[2]) == 2:
                        parts[2] = "20" + parts[2]
                        cc_details = "|".join(parts)
                    valid_ccs.append(cc_details)
                    matched = True
                    break
        if not matched:
            continue
    return valid_ccs

class FCCCommandFilter(BaseFilter):
    async def __call__(self, message: Message):
        if not message.text:
            return False
        for prefix in BotCommands:
            if message.text.lower().startswith(f"{prefix}fcc") or message.text.lower().startswith(f"{prefix}filter"):
                return True
        return False

@dp.message(FCCCommandFilter())
@new_task
@SmartDefender
async def handle_fcc_command(message: Message, bot: Bot):
    LOGGER.info(f"Received /fcc command from user: {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
    progress_message = None
    file_path = None
    file_name = None
    try:
        if not message.reply_to_message or not message.reply_to_message.document or not message.reply_to_message.document.file_name.endswith('.txt'):
            progress_message = await send_message(
                chat_id=message.chat.id,
                text="<b>⚠️ Reply to a text file to filter CC details❌</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.warning(f"Invalid reply for /fcc command by user: {message.from_user.id}")
            return
        file_size_mb = message.reply_to_message.document.file_size / (1024 * 1024)
        if file_size_mb > MAX_TXT_SIZE:
            progress_message = await send_message(
                chat_id=message.chat.id,
                text=f"<b>⚠️ File size exceeds the {MAX_TXT_SIZE}MB limit❌</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.warning(f"File size exceeds limit for /fcc command by user: {message.from_user.id}")
            return
        progress_message = await send_message(
            chat_id=message.chat.id,
            text="<b>Filtering CCs, Please Wait...✨</b>",
            parse_mode=ParseMode.HTML
        )
        start_time = time.time()
        file_id = message.reply_to_message.document.file_id
        file_info = await bot.get_file(file_id)
        file_path = f"downloads/{file_id}.txt"
        os.makedirs('downloads', exist_ok=True)
        await bot.download_file(file_info.file_path, file_path)
        with open(file_path, 'r') as file:
            content = file.readlines()
        valid_ccs = await filter_valid_cc(content)
        end_time = time.time()
        time_taken = end_time - start_time
        if not valid_ccs:
            await progress_message.edit_text(
                text="<b>❌ No valid credit card details found in the file.</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"No valid CCs found for /fcc command in chat {message.chat.id}")
            return
        total_amount = len(valid_ccs)
        total_size = f"{os.path.getsize(file_path) / 1024:.2f} KB"
        total_lines = len(valid_ccs)
        await delete_messages(message.chat.id, progress_message.message_id)
        if total_amount > 10:
            file_name = f"downloads/Filtered_CCs_{total_amount}.txt"
            with open(file_name, 'w') as f:
                f.write("\n".join(valid_ccs))
            caption = (
                "<b>Smart CC Filtering → Successful ✅</b>\n"
                "<b>━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>⊗ Total Amount:</b> {total_amount}\n"
                f"<b>⊗ Total Size:</b> {total_size}\n"
                f"<b>⊗ Total Lines:</b> {total_lines}\n"
                "<b>━━━━━━━━━━━━━━━━━</b>\n"
                "<b>Smart CC Filter → Activated ✅</b>"
            )
            buttons = SmartButtons()
            buttons.button(text="Join For Updates", url=UPDATE_CHANNEL_URL)
            try:
                await bot.send_document(
                    chat_id=message.chat.id,
                    document=FSInputFile(path=file_name),
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=buttons.build_menu(b_cols=1)
                )
                LOGGER.info(f"Successfully sent filtered CC document to chat {message.chat.id}")
            except Exception as e:
                LOGGER.error(f"Error sending document to chat {message.chat.id}: {str(e)}")
                await Smart_Notify(bot, "fcc", e, message)
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Sorry, an error occurred while sending the file</b>",
                    parse_mode=ParseMode.HTML
                )
            finally:
                clean_download(file_name)
        else:
            formatted_ccs = "\n".join(f"<code>{cc}</code>" for cc in valid_ccs)
            response_message = (
                "<b>Smart CC Filtering → Successful ✅</b>\n"
                "<b>━━━━━━━━━━━━━━━━━</b>\n" +
                formatted_ccs + "\n" +
                "<b>━━━━━━━━━━━━━━━━━</b>\n"
                "<b>Smart CC Filter → Activated ✅</b>"
            )
            await send_message(
                chat_id=message.chat.id,
                text=response_message,
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Successfully sent filtered CCs to chat {message.chat.id}")
    except Exception as e:
        LOGGER.error(f"Error processing /fcc command in chat {message.chat.id}: {str(e)}")
        await Smart_Notify(bot, "fcc", e, message)
        if progress_message:
            try:
                await progress_message.edit_text(
                    text="<b>❌ Sorry, an error occurred while filtering CCs</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Edited progress message with error in chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                await Smart_Notify(bot, "fcc", edit_e, message)
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Sorry, an error occurred while filtering CCs</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Sent error message to chat {message.chat.id}")
        else:
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Sorry, an error occurred while filtering CCs</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Sent error message to chat {message.chat.id}")
    finally:
        if file_path:
            clean_download(file_path)