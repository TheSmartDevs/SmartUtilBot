# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
#  Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
from aiogram import Bot
from aiogram.filters import Command, BaseFilter
from aiogram.types import Message
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
from collections import Counter
import os
import time
import asyncio

class TopBinCommandFilter(BaseFilter):
    async def __call__(self, message: Message):
        if not message.text:
            return False
        for prefix in BotCommands:
            if message.text.lower().startswith(f"{prefix}topbin"):
                return True
        return False

@dp.message(TopBinCommandFilter())
@new_task
@SmartDefender
async def handle_topbin_command(message: Message, bot: Bot):
    progress_message = None
    file_path = None
    try:
        if not message.reply_to_message or not message.reply_to_message.document or not message.reply_to_message.document.file_name.endswith('.txt'):
            progress_message = await send_message(
                chat_id=message.chat.id,
                text="<b>⚠️ Reply to a text file containing credit cards to check top bins❌</b>",
                parse_mode=ParseMode.HTML
            )
            return
        file_size_mb = message.reply_to_message.document.file_size / (1024 * 1024)
        if file_size_mb > MAX_TXT_SIZE:
            progress_message = await send_message(
                chat_id=message.chat.id,
                text=f"<b>⚠️ File size exceeds the {MAX_TXT_SIZE}MB limit❌</b>",
                parse_mode=ParseMode.HTML
            )
            return
        progress_message = await send_message(
            chat_id=message.chat.id,
            text="<b>Finding Top Bins...✨</b>",
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
        bin_counter = Counter([line.strip()[:6] for line in content if len(line.strip()) >= 6])
        top_bins = bin_counter.most_common(20)
        end_time = time.time()
        time_taken = end_time - start_time
        if not top_bins:
            await progress_message.edit_text(
                text="<b>❌ No BIN data found in the file.</b>",
                parse_mode=ParseMode.HTML
            )
            return
        response_message = (
            "<b>Smart Top Bin Find → Successful ✅</b>\n"
            "<b>━━━━━━━━━━━━━━━━━</b>\n" +
            "\n".join(f"<b>⊗ BIN:</b> <code>{bin}</code> - <b>Amount:</b> <code>{count}</code>" for bin, count in top_bins) + "\n" +
            "<b>━━━━━━━━━━━━━━━━━</b>\n"
            "<b>Smart Top Bin Finder → Activated ✅</b>"
        )
        buttons = SmartButtons()
        buttons.button(text="Join For Updates", url=UPDATE_CHANNEL_URL)
        await delete_messages(message.chat.id, progress_message.message_id)
        await send_message(
            chat_id=message.chat.id,
            text=response_message,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            reply_markup=buttons.build_menu(b_cols=1)
        )
    except Exception as e:
        await Smart_Notify(bot, "topbin", e, message)
        if progress_message:
            try:
                await progress_message.edit_text(
                    text="<b>❌ Sorry, an error occurred while finding top BINs</b>",
                    parse_mode=ParseMode.HTML
                )
            except TelegramBadRequest as edit_e:
                await Smart_Notify(bot, "topbin", edit_e, message)
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Sorry, an error occurred while finding top BINs</b>",
                    parse_mode=ParseMode.HTML
                )
        else:
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Sorry, an error occurred while finding top BINs</b>",
                parse_mode=ParseMode.HTML
            )
    finally:
        clean_download()