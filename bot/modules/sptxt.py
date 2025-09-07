# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
#  Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
import os
import aiofiles
import asyncio
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.enums import ParseMode, ChatType
from bot import dp, SmartAIO
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.notify import Smart_Notify
from bot.helpers.logger import LOGGER
from bot.helpers.commands import BotCommands
from bot.helpers.defend import SmartDefender
from config import MAX_TXT_SIZE

logger = LOGGER

async def process_file(file_path, line_limit):
    async with aiofiles.open(file_path, "r", encoding='utf-8', errors='ignore') as file:
        lines = await file.readlines()
    total_lines = len(lines)
    split_files = []
    file_index = 1
    for start in range(0, total_lines, line_limit):
        end = start + line_limit
        split_file_path = f"{file_path}_part_{file_index}.txt"
        async with aiofiles.open(split_file_path, "w", encoding='utf-8') as split_file:
            await split_file.writelines(lines[start:end])
        split_files.append(split_file_path)
        file_index += 1
    return split_files

@dp.message(Command(commands=["sptxt"], prefix=BotCommands))
@new_task
@SmartDefender
async def split_text(message: Message, bot: Bot):
    if message.chat.type != ChatType.PRIVATE:
        await send_message(
            chat_id=message.chat.id,
            text="<b>You only can Split text in private chat⚠️</b>",
            parse_mode=ParseMode.HTML
        )
        return
    user_id = message.from_user.id
    logger.info(f"Command received from user {user_id} in chat {message.chat.id}: {message.text}")
    if not message.reply_to_message or not message.reply_to_message.document or not message.reply_to_message.document.file_name.endswith(".txt"):
        await send_message(
            chat_id=message.chat.id,
            text="<b>⚠️ Please Reply To A Txt File And Give Amount To Split</b>",
            parse_mode=ParseMode.HTML
        )
        return
    file_size_mb = message.reply_to_message.document.file_size / (1024 * 1024)
    if file_size_mb > MAX_TXT_SIZE:
        await send_message(
            chat_id=message.chat.id,
            text="<b>⚠️ File size exceeds the 10MB limit❌</b>",
            parse_mode=ParseMode.HTML
        )
        return
    try:
        line_limit = int(get_args(message)[0])
    except (IndexError, ValueError):
        await send_message(
            chat_id=message.chat.id,
            text="<b>⚠️ Please Provide A Valid Line Limit</b>",
            parse_mode=ParseMode.HTML
        )
        return
    processing_msg = await send_message(
        chat_id=message.chat.id,
        text="<b>Processing Text Split..✨</b>",
        parse_mode=ParseMode.HTML
    )
    try:
        file_id = message.reply_to_message.document.file_id
        os.makedirs("./downloads", exist_ok=True)
        file_path = f"./downloads/sptxt_{user_id}_{int(asyncio.get_event_loop().time())}.txt"
        await bot.download(file=file_id, destination=file_path)
        split_files = await process_file(file_path, line_limit)
        try:
            await delete_messages(
                chat_id=message.chat.id,
                message_ids=[processing_msg.message_id]
            )
        except Exception as e:
            logger.warning(f"[{user_id}] Failed to delete processing message: {e}")
        for split_file in split_files:
            await bot.send_document(
                chat_id=message.chat.id,
                document=FSInputFile(split_file)
            )
            clean_download(split_file)
        clean_download(file_path)
    except Exception as e:
        logger.error(f"[{user_id}] Error processing /sptxt: {e}")
        try:
            await delete_messages(
                chat_id=message.chat.id,
                message_ids=[processing_msg.message_id]
            )
        except Exception as e:
            logger.warning(f"[{user_id}] Failed to delete processing message: {e}")
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Error processing text split</b>",
            parse_mode=ParseMode.HTML
        )
        clean_download(file_path)
        await Smart_Notify(bot, "/sptxt", e, message)