import asyncio
import secrets
import urllib.parse
from datetime import datetime
from mimetypes import guess_type
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from pyrogram.enums import ParseMode as SmartParseMode
from pyrogram.types import Message as SmartMessage
from pyrogram.enums import ChatMemberStatus
from bot import dp, SmartPyro
from bot.helpers.utils import new_task
from bot.helpers.botutils import send_message, delete_messages
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.buttons import SmartButtons
from bot.helpers.defend import SmartDefender
from config import LOG_CHANNEL_ID
import os

logger = LOGGER

BASE_URL = os.getenv("BASE_URL", "http://147.93.19.133:8000")

async def get_file_properties(message: Message):
    file_name = None
    file_size = 0
    mime_type = None
    resolution = None
    if message.document:
        file_name = message.document.file_name
        file_size = message.document.file_size
        mime_type = message.document.mime_type
    elif message.video:
        file_name = getattr(message.video, 'file_name', None)
        file_size = message.video.file_size
        mime_type = message.video.mime_type
        resolution = f"{message.video.width}x{message.video.height}" if message.video.width and message.video.height else None
    elif message.audio:
        file_name = getattr(message.audio, 'file_name', None)
        file_size = message.audio.file_size
        mime_type = message.audio.mime_type
    elif message.photo:
        file_name = None
        file_size = message.photo[-1].file_size
        mime_type = "image/jpeg"
        resolution = f"{message.photo[-1].width}x{message.photo[-1].height}" if message.photo[-1].width and message.photo[-1].height else None
    elif message.video_note:
        file_name = None
        file_size = message.video_note.file_size
        mime_type = "video/mp4"
    if not file_name:
        attributes = {
            "video": "mp4",
            "audio": "mp3",
            "video_note": "mp4",
            "photo": "jpg",
        }
        for attribute in attributes:
            if getattr(message, attribute, None):
                file_type, file_format = attribute, attributes[attribute]
                break
            else:
                raise ValueError("Invalid media type.")
        date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        file_name = f"{file_type}-{date}"
        if resolution:
            file_name += f" ({resolution})"
        file_name += f".{file_format}"
    if not mime_type:
        mime_type = guess_type(file_name)[0] or "application/octet-stream"
    return file_name, file_size, mime_type

async def format_file_size(file_size: int):
    if file_size < 1024 * 1024:
        size = file_size / 1024
        unit = "KB"
    elif file_size < 1024 * 1024 * 1024:
        size = file_size / (1024 * 1024)
        unit = "MB"
    else:
        size = file_size / (1024 * 1024 * 1024)
        unit = "GB"
    return f"{size:.2f} {unit}"

async def handle_file_download(message: Message, bot: Bot):
    user_id = message.from_user.id if message.from_user else None
    if not message.reply_to_message:
        await send_message(
            chat_id=message.chat.id,
            text="<b>Please Reply To File For Link</b>",
            parse_mode=ParseMode.HTML
        )
        return
    reply_message = message.reply_to_message
    if not (reply_message.document or reply_message.video or reply_message.photo or reply_message.audio or reply_message.video_note):
        await send_message(
            chat_id=message.chat.id,
            text="<b>Please Reply To A Valid File</b>",
            parse_mode=ParseMode.HTML
        )
        return
    processing_msg = await send_message(
        chat_id=message.chat.id,
        text="<b>Processing Your File...</b>",
        parse_mode=ParseMode.HTML
    )
    try:
        bot_member = await SmartPyro.get_chat_member(LOG_CHANNEL_ID, "me")
        if bot_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            await processing_msg.edit_text(
                "<b>Error: Bot must be an admin in the log channel</b>",
                parse_mode=ParseMode.HTML
            )
            return
        code = f"{secrets.token_urlsafe(16)}-{user_id}"
        file_name, file_size, mime_type = await get_file_properties(reply_message)
        file_id = None
        if message.chat.id == LOG_CHANNEL_ID:
            file_id = reply_message.message_id
            sent = await SmartPyro.copy_message(
                chat_id=LOG_CHANNEL_ID,
                from_chat_id=LOG_CHANNEL_ID,
                message_id=reply_message.message_id,
                caption=code,
                parse_mode=SmartParseMode.HTML
            )
            file_id = sent.id
        else:
            sent = await reply_message.forward(LOG_CHANNEL_ID)
            file_id = sent.message_id
            sent = await SmartPyro.copy_message(
                chat_id=LOG_CHANNEL_ID,
                from_chat_id=LOG_CHANNEL_ID,
                message_id=file_id,
                caption=code,
                parse_mode=SmartParseMode.HTML
            )
            file_id = sent.id
        quoted_code = urllib.parse.quote(code)
        base_url = BASE_URL.rstrip('/')
        download_link = f"{base_url}/dl/{file_id}?code={quoted_code}"
        is_video = mime_type.startswith('video') or reply_message.video or reply_message.video_note
        stream_link = f"{base_url}/dl/{file_id}?code={quoted_code}=stream" if is_video else None
        smart_buttons = SmartButtons()
        smart_buttons.button("🚀 Download", url=download_link)
        if stream_link:
            smart_buttons.button("🖥️ Stream", url=stream_link)
        keyboard = smart_buttons.build_menu(b_cols=2)
        response = (
            f"✨ Your Links are Ready! ✨\n\n"
            f"{file_name}\n\n"
            f"📂 File Size: {await format_file_size(file_size)}\n\n"
            f"🚀 Download Link: {download_link}\n\n"
        )
        if stream_link:
            response += f"🖥️ Stream Link: {stream_link}\n\n"
        response += "⌛️ Note: Links remain active while the bot is running and the file is accessible."
        await processing_msg.edit_text(
            text=response,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
        logger.info(f"Generated links for file_id: {file_id}, download: {download_link}, stream: {stream_link}")
    except Exception as e:
        logger.error(f"Error generating links for file_id: {file_id if 'file_id' in locals() else 'unknown'}, error: {str(e)}")
        await Smart_Notify(bot, f"{BotCommands}fdl", e, processing_msg)
        await processing_msg.edit_text(
            f"<b>Error: Failed to generate link - {str(e)}</b>",
            parse_mode=ParseMode.HTML
        )

@dp.message(Command(commands=["fdl"], prefix=BotCommands))
@new_task
@SmartDefender
async def fdl_command(message: Message, bot: Bot):
    await handle_file_download(message, bot)