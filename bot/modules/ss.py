# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
#  Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
import os
import aiohttp
import time
import aiofiles
import asyncio
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from pyrogram.enums import ParseMode as SmartParseMode
from pyrogram.types import Message as SmartMessage
from bot import dp, SmartPyro
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.defend import SmartDefender
from config import WEB_SS_KEY
from urllib.parse import quote

logger = LOGGER
MAX_FILE_SIZE = 5 * 1024 * 1024

def validate_url(url: str) -> bool:
    return '.' in url and len(url) < 2048

def normalize_url(url: str) -> str:
    return url if url.startswith(('http://', 'https://')) else f"https://{url}"

async def fetch_screenshot(url: str, bot: Bot) -> bytes:
    api_url = f"https://api.thumbnail.ws/api/{WEB_SS_KEY}/thumbnail/get?url={quote(url)}&width=1280"
    timeout = aiohttp.ClientTimeout(total=10)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(api_url) as response:
                response.raise_for_status()
                content_type = response.headers.get('Content-Type', '')
                if 'image' not in content_type:
                    raise ValueError(f"Unexpected content type: {content_type}")
                content_length = int(response.headers.get('Content-Length', 0))
                if content_length > MAX_FILE_SIZE:
                    raise ValueError(f"Screenshot too large ({content_length / 1024 / 1024:.1f}MB)")
                return await response.read()
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as e:
        logger.error(f"Failed to fetch screenshot for {url}: {e}")
        await Smart_Notify(bot, f"{BotCommands}ss", e, None)
        return None

async def save_screenshot(url: str, timestamp: int, bot: Bot) -> str:
    screenshot_bytes = await fetch_screenshot(url, bot)
    if not screenshot_bytes:
        return None
    temp_file = f"screenshot_{timestamp}_{hash(url)}.jpg"
    async with aiofiles.open(temp_file, 'wb') as file:
        await file.write(screenshot_bytes)
    file_size = os.path.getsize(temp_file)
    if file_size > MAX_FILE_SIZE:
        clean_download(temp_file)
        return None
    return temp_file

async def capture_screenshots(message: Message, bot: Bot, urls: list) -> None:
    user_id = message.from_user.id if message.from_user else None
    if not urls:
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Please provide at least one URL after the command</b>",
            parse_mode=ParseMode.HTML
        )
        return
    for url in urls:
        if not validate_url(url):
            await send_message(
                chat_id=message.chat.id,
                text=f"<b>❌ Invalid URL format: {url}</b>",
                parse_mode=ParseMode.HTML
            )
            return
    processing_msg = await send_message(
        chat_id=message.chat.id,
        text="<b>Capturing ScreenShots Please Wait</b>",
        parse_mode=ParseMode.HTML
    )
    timestamp = int(time.time())
    tasks = [save_screenshot(normalize_url(url), timestamp, bot) for url in urls]
    temp_files = await asyncio.gather(*tasks, return_exceptions=True)
    try:
        for i, temp_file in enumerate(temp_files):
            if isinstance(temp_file, Exception):
                logger.error(f"Error processing {urls[i]}: {temp_file}")
                continue
            if temp_file:
                async with aiofiles.open(temp_file, 'rb'):
                    await SmartPyro.send_photo(
                        chat_id=message.chat.id,
                        photo=temp_file,
                        parse_mode=SmartParseMode.HTML
                    )
                clean_download(temp_file)
        await delete_messages(message.chat.id, [processing_msg.message_id])
    except Exception as e:
        logger.error(f"Error in capture_screenshots: {e}")
        await Smart_Notify(bot, f"{BotCommands}ss", e, processing_msg)
        await processing_msg.edit_text("<b>Sorry Bro SS Capture API Dead</b>", parse_mode=ParseMode.HTML)

@dp.message(Command(commands=["ss"], prefix=BotCommands))
@new_task
@SmartDefender
async def ss_command(message: Message, bot: Bot):
    urls = get_args(message)
    await capture_screenshots(message, bot, urls)