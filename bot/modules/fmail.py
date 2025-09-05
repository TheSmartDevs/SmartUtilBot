import re
import os
import time
import aiofiles
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.enums import ParseMode, ChatType
from bot import dp, SmartAIO
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.notify import Smart_Notify
from bot.helpers.logger import LOGGER
from bot.helpers.buttons import SmartButtons
from bot.helpers.commands import BotCommands
from config import MAX_TXT_SIZE, UPDATE_CHANNEL_URL

logger = LOGGER

async def filter_emails(content):
    email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
    emails = [line.split(':')[0].strip() for line in content if email_pattern.match(line.split(':')[0])]
    return emails

async def filter_email_pass(content):
    email_pass_pattern = re.compile(r'^([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}):(.+)$')
    email_passes = []
    for line in content:
        match = email_pass_pattern.match(line)
        if match:
            email = match.group(1)
            password = match.group(2).split()[0]
            email_passes.append(f"{email}:{password}")
    return email_passes

@dp.message(Command(commands=["fmail"], prefix=BotCommands))
@new_task
async def handle_fmail_command(message: Message, bot: Bot):
    if message.chat.type not in [ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP]:
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ This command only works in private or group chats</b>",
            parse_mode=ParseMode.HTML
        )
        return
    user_id = message.from_user.id
    logger.info(f"Command received from user {user_id} in chat {message.chat.id}: {message.text}")
    if not message.reply_to_message or not message.reply_to_message.document or not message.reply_to_message.document.file_name.endswith('.txt'):
        await send_message(
            chat_id=message.chat.id,
            text="<b>⚠️ Reply to a message with a text file❌</b>",
            parse_mode=ParseMode.HTML
        )
        return
    start_time = time.time()
    temp_msg = await send_message(
        chat_id=message.chat.id,
        text="<b>Fetching And Filtering Mails...✨</b>",
        parse_mode=ParseMode.HTML
    )
    try:
        file_id = message.reply_to_message.document.file_id
        os.makedirs("./downloads", exist_ok=True)
        file_path = f"./downloads/fmail_{user_id}_{int(start_time)}.txt"
        await bot.download(file=file_id, destination=file_path)
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb > MAX_TXT_SIZE:
            await SmartAIO.delete_message(
                chat_id=message.chat.id,
                message_id=temp_msg.message_id
            )
            await send_message(
                chat_id=message.chat.id,
                text="<b>⚠️ File size exceeds the 15MB limit❌</b>",
                parse_mode=ParseMode.HTML
            )
            clean_download(file_path)
            return
        async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
            content = await file.readlines()
        emails = await filter_emails(content)
        if not emails:
            await SmartAIO.delete_message(
                chat_id=message.chat.id,
                message_id=temp_msg.message_id
            )
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ No valid emails found in the file.</b>",
                parse_mode=ParseMode.HTML
            )
            clean_download(file_path)
            return
        user_full_name = f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip() if message.from_user else "Unknown User"
        user_profile_url = f"https://t.me/{message.from_user.username}" if message.from_user and message.from_user.username else None
        user_link = f'<a href="{user_profile_url}">{user_full_name}</a>' if user_profile_url else user_full_name
        time_taken = round(time.time() - start_time, 2)
        total_lines = len(content)
        total_mails = len(emails)
        caption = (
            f"<b>Smart Mail Extraction Complete ✅</b>\n"
            f"<b>━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>⊗ Total Size:</b> <code>{file_size_mb:.2f} MB</code>\n"
            f"<b>⊗ Total Mails:</b> <code>{total_mails}</code>\n"
            f"<b>⊗ Total Lines:</b> <code>{total_lines}</code>\n"
            f"<b>⊗ Time Taken:</b> <code>{time_taken} seconds</code>\n"
            f"<b>━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>Requested By {user_link}</b>"
        )
        buttons = SmartButtons()
        buttons.button(text="Join For Updates", callback_data="join_updates", url=UPDATE_CHANNEL_URL)
        reply_markup = buttons.build_menu(b_cols=1)
        if len(emails) > 10:
            file_name = f"./downloads/processed_fmail_{user_id}_{int(start_time)}.txt"
            async with aiofiles.open(file_name, 'w', encoding='utf-8') as f:
                await f.write("\n".join(emails))
            await SmartAIO.delete_message(
                chat_id=message.chat.id,
                message_id=temp_msg.message_id
            )
            await bot.send_document(
                chat_id=message.chat.id,
                document=FSInputFile(file_name),
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
            clean_download(file_name)
        else:
            formatted_emails = '\n'.join(f'<code>{email}</code>' for email in emails)
            await SmartAIO.delete_message(
                chat_id=message.chat.id,
                message_id=temp_msg.message_id
            )
            await send_message(
                chat_id=message.chat.id,
                text=f"{caption}\n\n{formatted_emails}",
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
        clean_download(file_path)
    except Exception as e:
        logger.error(f"[{user_id}] Error processing /fmail: {e}")
        await SmartAIO.delete_message(
            chat_id=message.chat.id,
            message_id=temp_msg.message_id
        )
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Error processing the file.</b>",
            parse_mode=ParseMode.HTML
        )
        clean_download(file_path)
        await Smart_Notify(bot, "/fmail", e, message)

@dp.message(Command(commands=["fpass"], prefix=BotCommands))
@new_task
async def handle_fpass_command(message: Message, bot: Bot):
    if message.chat.type not in [ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP]:
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ This command only works in private or group chats</b>",
            parse_mode=ParseMode.HTML
        )
        return
    user_id = message.from_user.id
    logger.info(f"Command received from user {user_id} in chat {message.chat.id}: {message.text}")
    if not message.reply_to_message or not message.reply_to_message.document or not message.reply_to_message.document.file_name.endswith('.txt'):
        await send_message(
            chat_id=message.chat.id,
            text="<b>⚠️ Reply to a message with a text file❌</b>",
            parse_mode=ParseMode.HTML
        )
        return
    start_time = time.time()
    temp_msg = await send_message(
        chat_id=message.chat.id,
        text="<b>Filtering And Extracting Mail Pass...✨</b>",
        parse_mode=ParseMode.HTML
    )
    try:
        file_id = message.reply_to_message.document.file_id
        os.makedirs("./downloads", exist_ok=True)
        file_path = f"./downloads/fpass_{user_id}_{int(start_time)}.txt"
        await bot.download(file=file_id, destination=file_path)
        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        if file_size_mb > MAX_TXT_SIZE:
            await SmartAIO.delete_message(
                chat_id=message.chat.id,
                message_id=temp_msg.message_id
            )
            await send_message(
                chat_id=message.chat.id,
                text="<b>⚠️ File size exceeds the 15MB limit❌</b>",
                parse_mode=ParseMode.HTML
            )
            clean_download(file_path)
            return
        async with aiofiles.open(file_path, 'r', encoding='utf-8', errors='ignore') as file:
            content = await file.readlines()
        email_passes = await filter_email_pass(content)
        if not email_passes:
            await SmartAIO.delete_message(
                chat_id=message.chat.id,
                message_id=temp_msg.message_id
            )
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ No Mail Pass Combo Found</b>",
                parse_mode=ParseMode.HTML
            )
            clean_download(file_path)
            return
        user_full_name = f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip() if message.from_user else "Unknown User"
        user_profile_url = f"https://t.me/{message.from_user.username}" if message.from_user and message.from_user.username else None
        user_link = f'<a href="{user_profile_url}">{user_full_name}</a>' if user_profile_url else user_full_name
        time_taken = round(time.time() - start_time, 2)
        total_lines = len(content)
        total_mails = len(email_passes)
        total_pass = len(email_passes)
        caption = (
            f"<b>Smart Mail-Pass Combo Process Complete ✅</b>\n"
            f"<b>━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>⊗ Total Size:</b> <code>{file_size_mb:.2f} MB</code>\n"
            f"<b>⊗ Total Mails:</b> <code>{total_mails}</code>\n"
            f"<b>⊗ Total Pass:</b> <code>{total_pass}</code>\n"
            f"<b>⊗ Total Lines:</b> <code>{total_lines}</code>\n"
            f"<b>⊗ Time Taken:</b> <code>{time_taken} seconds</code>\n"
            f"<b>━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>Requested By {user_link}</b>"
        )
        buttons = SmartButtons()
        buttons.button(text="Join For Updates", callback_data="join_updates", url=UPDATE_CHANNEL_URL)
        reply_markup = buttons.build_menu(b_cols=1)
        if len(email_passes) > 10:
            file_name = f"./downloads/processed_fpass_{user_id}_{int(start_time)}.txt"
            async with aiofiles.open(file_name, 'w', encoding='utf-8') as f:
                await f.write("\n".join(email_passes))
            await SmartAIO.delete_message(
                chat_id=message.chat.id,
                message_id=temp_msg.message_id
            )
            await bot.send_document(
                chat_id=message.chat.id,
                document=FSInputFile(file_name),
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
            clean_download(file_name)
        else:
            formatted_email_passes = '\n'.join(f'<code>{email_pass}</code>' for email_pass in email_passes)
            await SmartAIO.delete_message(
                chat_id=message.chat.id,
                message_id=temp_msg.message_id
            )
            await send_message(
                chat_id=message.chat.id,
                text=f"{caption}\n\n{formatted_email_passes}",
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
        clean_download(file_path)
    except Exception as e:
        logger.error(f"[{user_id}] Error processing /fpass: {e}")
        await SmartAIO.delete_message(
            chat_id=message.chat.id,
            message_id=temp_msg.message_id
        )
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Error processing the file.</b>",
            parse_mode=ParseMode.HTML
        )
        clean_download(file_path)
        await Smart_Notify(bot, "/fpass", e, message)