# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
#  Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
import os
import re
import asyncio
import time
import aiohttp
import aiofiles
from pathlib import Path
from typing import Optional
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from pyrogram.enums import ParseMode as SmartParseMode
from pyrogram.types import Message as SmartMessage
from moviepy import VideoFileClip
from bot import dp, SmartPyro
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.defend import SmartDefender
from bot.helpers.pgbar import progress_bar
from config import A360APIBASEURL
import base64

logger = LOGGER

class Config:
    TEMP_DIR = Path("./downloads")

Config.TEMP_DIR.mkdir(exist_ok=True)

class TwitterDownloader:
    async def sanitize_filename(self, title: str) -> str:
        title = re.sub(r'[<>:"/\\|?*]', '', title[:50]).strip()
        return f"{title.replace(' ', '_')}_{int(time.time())}"
    async def download_file(self, session: aiohttp.ClientSession, url: str, dest: Path, bot: Bot) -> None:
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    async with aiofiles.open(dest, mode='wb') as f:
                        async for chunk in response.content.iter_chunked(1024 * 1024):
                            await f.write(chunk)
                else:
                    raise Exception(f"Failed to download file: {response.status}")
        except Exception as e:
            await Smart_Notify(bot, f"{BotCommands}tx", e, None)
            raise
    async def download_video(self, url: str, downloading_message: Message, bot: Bot) -> Optional[dict]:
        Config.TEMP_DIR.mkdir(exist_ok=True)
        api_url = f"{A360APIBASEURL}/thrd/twit?url={url}"
        try:
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(limit_per_host=10),
                timeout=aiohttp.ClientTimeout(total=30)
            ) as session:
                async with session.get(api_url) as response:
                    if response.status == 200:
                        data = await response.json()
                        video_urls = data.get("results", {}).get("video_urls", [])
                        if not video_urls:
                            await downloading_message.edit_text("<b>Unable To Extract Video URL</b>", parse_mode=ParseMode.HTML)
                            return None
                        def get_resolution(video_url):
                            try:
                                file_param = video_url.split('file=')[1]
                                decoded_url = base64.b64decode(file_param + '==').decode('utf-8')
                                match = re.search(r'(\d+x\d+)', decoded_url)
                                if match:
                                    width, height = map(int, match.group(1).split('x'))
                                    return width * height
                                return 0
                            except:
                                return 0
                        video_url = max(video_urls, key=get_resolution)
                        title = data.get("results", {}).get("title", "Twitter Video")
                        await downloading_message.edit_text("<b>Found ☑️ Downloading...</b>", parse_mode=ParseMode.HTML)
                        safe_title = await self.sanitize_filename(title)
                        filename = Config.TEMP_DIR / f"{safe_title}.mp4"
                        await self.download_file(session, video_url, filename, bot)
                        return {
                            'title': title,
                            'filename': str(filename),
                            'webpage_url': url
                        }
                    return None
        except aiohttp.ClientError as e:
            await Smart_Notify(bot, f"{BotCommands}tx", e, downloading_message)
            return None
        except asyncio.TimeoutError:
            await Smart_Notify(bot, f"{BotCommands}tx", asyncio.TimeoutError("Request to Twitter API timed out"), downloading_message)
            return None
        except Exception as e:
            await Smart_Notify(bot, f"{BotCommands}tx", e, downloading_message)
            return None

async def tx_handler(message: Message, bot: Bot):
    twitter_downloader = TwitterDownloader()
    url = None
    if message.reply_to_message and message.reply_to_message.text:
        match = re.search(r"https?://(x\.com|twitter\.com)/\S+", message.reply_to_message.text)
        if match:
            url = match.group(0)
    if not url:
        args = get_args(message)
        if args:
            match = re.search(r"https?://(x\.com|twitter\.com)/\S+", args[0])
            if match:
                url = match.group(0)
    if not url:
        await send_message(
            chat_id=message.chat.id,
            text="<b>Bro Please Provide A Twitter URL</b>",
            parse_mode=ParseMode.HTML
        )
        return
    downloading_message = await send_message(
        chat_id=message.chat.id,
        text="<b>Searching The Media</b>",
        parse_mode=ParseMode.HTML
    )
    try:
        video_info = await twitter_downloader.download_video(url, downloading_message, bot)
        if not video_info:
            await downloading_message.edit_text("<b>Invalid Video URL or Video is Private</b>", parse_mode=ParseMode.HTML)
            return
        title = video_info['title']
        filename = video_info['filename']
        webpage_url = video_info['webpage_url']
        video_clip = VideoFileClip(filename)
        duration = video_clip.duration
        duration_str = f"{int(duration // 60)}m {int(duration % 60)}s"
        video_clip.close()
        user_info = (
            f"<a href=\"tg://user?id={message.from_user.id}\">{message.from_user.first_name}{' ' + message.from_user.last_name if message.from_user.last_name else ''} {'🇧🇩' if message.from_user.language_code == 'bn' else ''}</a>" if message.from_user
            else f"<a href=\"https://t.me/{message.chat.username or 'this group'}\">{message.chat.title}</a>"
        )
        caption = (
            f"🎥 <b>Title:</b> <code>{title}</code>\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>🔗 Url:</b> <a href=\"{webpage_url}\">Watch On Twitter</a>\n"
            f"<b>⏱️ Duration:</b> {duration_str}\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>Downloaded By</b> {user_info}"
        )
        async with aiofiles.open(filename, 'rb'):
            start_time = time.time()
            last_update_time = [start_time]
            await SmartPyro.send_video(
                chat_id=message.chat.id,
                video=filename,
                supports_streaming=True,
                caption=caption,
                parse_mode=SmartParseMode.HTML,
                duration=int(duration),
                width=1280,
                height=720,
                progress=progress_bar,
                progress_args=(downloading_message, start_time, last_update_time)
            )
        await delete_messages(message.chat.id, [downloading_message.message_id])
        if os.path.exists(filename):
            clean_download(filename)
    except Exception as e:
        await Smart_Notify(bot, f"{BotCommands}tx", e, downloading_message)
        await downloading_message.edit_text("<b>Twitter Downloader API Dead</b>", parse_mode=ParseMode.HTML)

@dp.message(Command(commands=["tx", "x"], prefix=BotCommands))
@new_task
@SmartDefender
async def tx_command(message: Message, bot: Bot):
    await tx_handler(message, bot)