import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.enums import ParseMode

from bot import dp
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.utils import new_task, clean_download
from bot.helpers.notify import Smart_Notify
from bot.helpers.defend import SmartDefender

TEMP_DIR = Path("./downloads")
MAX_MESSAGES = 25
TEMP_DIR.mkdir(exist_ok=True)

def sanitize_filename(filename: str) -> str:
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    return filename.strip()[:100]

async def extract_text_from_message(message: Message) -> Optional[str]:
    text_content = []
    
    if message.text:
        text_content.append(message.text)
    elif message.caption:
        text_content.append(message.caption)
    
    if message.entities:
        for entity in message.entities:
            if entity.type in ["url", "text_link"]:
                if entity.type == "text_link":
                    text_content.append(f"\n{entity.url}")
    
    if message.caption_entities:
        for entity in message.caption_entities:
            if entity.type in ["url", "text_link"]:
                if entity.type == "text_link":
                    text_content.append(f"\n{entity.url}")
    
    return "\n".join(text_content) if text_content else None

async def collect_messages_chain(message: Message, count: int) -> list:
    collected = []
    current_message = message.reply_to_message
    
    if not current_message:
        return collected
    
    for i in range(count):
        if not current_message:
            break
        
        text = await extract_text_from_message(current_message)
        if text:
            collected.append({'text': text})
        
        if current_message.reply_to_message:
            current_message = current_message.reply_to_message
        else:
            break
    
    return list(reversed(collected))

async def create_text_file(messages: list, filename: str) -> tuple:
    timestamp = int(time.time())
    safe_filename = sanitize_filename(filename)
    if not safe_filename.endswith('.txt'):
        safe_filename += '.txt'
    
    filepath = TEMP_DIR / f"{safe_filename.rsplit('.', 1)[0]}_{timestamp}.txt"
    
    total_lines = 0
    total_chars = 0
    
    with open(filepath, 'w', encoding='utf-8') as f:
        for idx, msg in enumerate(messages, 1):
            f.write(msg['text'])
            if idx < len(messages):
                f.write("\n\n")
            
            total_lines += msg['text'].count('\n') + 1
            total_chars += len(msg['text'])
    
    return str(filepath), total_lines, total_chars

@dp.message(Command(commands=["m2t"], prefix=BotCommands))
@new_task
@SmartDefender
async def message_to_text_handler(message: Message, bot: Bot):
    user_id = message.from_user.id
    
    if not message.reply_to_message:
        await send_message(
            chat_id=message.chat.id,
            text="<b>Reply to a text message to convert → file</b>",
            parse_mode=ParseMode.HTML
        )
        LOGGER.info(f"User {user_id} used /m2t without replying to a message")
        return
    
    LOGGER.info(f"User {user_id} started /m2t command")
    
    try:
        args = get_args(message)
        
        filename = f"message_{int(time.time())}"
        count = 1
        
        if args:
            for arg in args:
                try:
                    num = int(arg)
                    count = min(max(num, 1), MAX_MESSAGES)
                except ValueError:
                    filename = arg
        
        progress_msg = await send_message(
            chat_id=message.chat.id,
            text=f"<b>📥 Collecting up to {count} message(s)...</b>",
            parse_mode=ParseMode.HTML
        )
        
        messages = await collect_messages_chain(message, count)
        
        if not messages:
            await delete_messages(message.chat.id, progress_msg.message_id)
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ No text content found in the replied message(s)!</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.warning(f"User {user_id} tried to convert messages with no text content")
            return
        
        actual_count = len(messages)
        
        await progress_msg.edit_text(
            f"<b>📝 Creating text file from {actual_count} message(s)...</b>",
            parse_mode=ParseMode.HTML
        )
        
        filepath, total_lines, total_chars = await create_text_file(messages, filename)
        
        await progress_msg.edit_text(
            "<b>📤 Uploading text file...</b>",
            parse_mode=ParseMode.HTML
        )
        
        caption = (
            f"<b>Message To Text Convert</b>\n"
            f"<b>━━━━━━━━━━━━━━</b>\n"
            f"<b>Messages:</b> <code>{actual_count}</code>\n"
            f"<b>Lines:</b> <code>{total_lines}</code>\n"
            f"<b>Characters:</b> <code>{total_chars}</code>\n"
            f"<b>━━━━━━━━━━━━━━</b>\n"
            f"<b>Thanks For Using SmartUtilBot 🤖</b>"
        )
        
        await bot.send_document(
            chat_id=message.chat.id,
            document=FSInputFile(filepath, filename=os.path.basename(filepath)),
            caption=caption,
            parse_mode=ParseMode.HTML
        )
        
        await delete_messages(message.chat.id, progress_msg.message_id)
        
        clean_download(filepath)
        
        LOGGER.info(f"User {user_id} successfully exported {actual_count} message(s) to text file")
        
    except Exception as e:
        await Smart_Notify(bot, "message_to_text_handler", e, message)
        LOGGER.error(f"Failed to convert messages to text for user {user_id}: {e}")
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Failed to convert messages to text!</b>",
            parse_mode=ParseMode.HTML
        )