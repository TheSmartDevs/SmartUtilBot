import asyncio
import urllib.parse
from datetime import datetime
from mimetypes import guess_type
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
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
import aiohttp

logger = LOGGER

FILE_API_URL = "http://161.97.132.210:5000"

async def check_api_health():
    try:
        timeout = aiohttp.ClientTimeout(total=5)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            base_url = FILE_API_URL.rstrip('/')
            async with session.get(f"{base_url}/") as response:
                if response.status == 200:
                    return True
                else:
                    return False
    except:
        return False

async def get_telegram_file_id(message: Message):
    if message.document:
        return message.document.file_id
    elif message.video:
        return message.video.file_id
    elif message.audio:
        return message.audio.file_id
    elif message.photo:
        return message.photo[-1].file_id
    elif message.video_note:
        return message.video_note.file_id
    else:
        return None

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

async def find_existing_message(code: str, limit: int = 100):
    try:
        async for message in SmartPyro.get_chat_history(LOG_CHANNEL_ID, limit=limit):
            if message.caption == code:
                return message.id
    except Exception as e:
        logger.error(f"Error searching for existing message: {e}")
    return None

async def handle_file_download(message: Message, bot: Bot):
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
        api_is_running = await check_api_health()
        if not api_is_running:
            await bot.edit_message_text(
                chat_id=processing_msg.chat.id,
                message_id=processing_msg.message_id,
                text="<b>Sorry File To Link Api Is Offline ❌</b>",
                parse_mode=ParseMode.HTML
            )
            logger.error("API is offline, stopping process")
            return
        bot_member = await SmartPyro.get_chat_member(LOG_CHANNEL_ID, "me")
        if bot_member.status not in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            await bot.edit_message_text(
                chat_id=processing_msg.chat.id,
                message_id=processing_msg.message_id,
                text="<b>Error: Bot must be an admin in the log channel</b>",
                parse_mode=ParseMode.HTML
            )
            return
        bot_me = await bot.get_me()
        bot_user_id = bot_me.id
        telegram_file_id = await get_telegram_file_id(reply_message)
        if not telegram_file_id:
            await bot.edit_message_text(
                chat_id=processing_msg.chat.id,
                message_id=processing_msg.message_id,
                text="<b>Error: Could not get file ID</b>",
                parse_mode=ParseMode.HTML
            )
            return
        file_name, file_size, mime_type = await get_file_properties(reply_message)
        code = f"{telegram_file_id}-{bot_user_id}"
        
        existing_message_id = await find_existing_message(code)
        
        if existing_message_id:
            message_id = existing_message_id
            logger.info(f"Found existing message for file_id: {telegram_file_id}, message_id: {message_id}")
        else:
            if message.chat.id == LOG_CHANNEL_ID:
                sent = await SmartPyro.copy_message(
                    chat_id=LOG_CHANNEL_ID,
                    from_chat_id=LOG_CHANNEL_ID,
                    message_id=reply_message.message_id,
                    caption=code
                )
                message_id = sent.id
            else:
                sent = await reply_message.forward(LOG_CHANNEL_ID)
                temp_id = sent.message_id
                sent = await SmartPyro.copy_message(
                    chat_id=LOG_CHANNEL_ID,
                    from_chat_id=LOG_CHANNEL_ID,
                    message_id=temp_id,
                    caption=code
                )
                message_id = sent.id
            logger.info(f"Created new message for file_id: {telegram_file_id}, message_id: {message_id}")
        
        quoted_code = urllib.parse.quote(code)
        base_url = FILE_API_URL.rstrip('/')
        download_link = f"{base_url}/dl/{message_id}?code={quoted_code}"
        is_video = mime_type.startswith('video') or reply_message.video or reply_message.video_note
        stream_link = f"{base_url}/dl/{message_id}?code={quoted_code}=stream" if is_video else None
        smart_buttons = SmartButtons()
        if is_video:
            smart_buttons.button("📥 Download", url=download_link)
            smart_buttons.button("▶️ Stream", url=stream_link)
            keyboard = smart_buttons.build_menu(b_cols=1)
        else:
            smart_buttons.button("📥 Download", url=download_link)
            keyboard = smart_buttons.build_menu(b_cols=1)
        if is_video:
            response = (
                f"<b>Video Name:</b> {file_name}\n"
                f"<b>Size:</b> {await format_file_size(file_size)}\n\n"
                f"<b>Download:</b> <code>{download_link}</code>\n\n"
                f"<b>Stream:</b> <code>{stream_link}</code>\n\n"
                f"<b>• Open in any browser or player.</b>\n"
                f"<b>• Stream works on PC & Android browsers.</b>"
            )
        else:
            response = (
                f"<b>File Name:</b> {file_name}\n"
                f"<b>File Size:</b> {await format_file_size(file_size)}\n\n"
                f"<b>File Link:</b> <code>{download_link}</code>\n\n"
                f"<b>Use the link to download the file directly.</b>"
            )
        await bot.edit_message_text(
            chat_id=processing_msg.chat.id,
            message_id=processing_msg.message_id,
            text=response,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
        logger.info(f"Generated links for message_id: {message_id}, telegram_file_id: {telegram_file_id}, download: {download_link}, stream: {stream_link}")
    except Exception as e:
        logger.error(f"Error generating links, error: {str(e)}")
        await Smart_Notify(bot, f"{BotCommands}fdl", e, processing_msg)
        await bot.edit_message_text(
            chat_id=processing_msg.chat.id,
            message_id=processing_msg.message_id,
            text=f"<b>Error: Failed to generate link - {str(e)}</b>",
            parse_mode=ParseMode.HTML
        )

@dp.message(Command(commands=["fdl"], prefix=BotCommands))
@new_task
@SmartDefender
async def fdl_command(message: Message, bot: Bot):
    await handle_file_download(message, bot)