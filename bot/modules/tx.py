import os
import re
import asyncio
import time
import json
import aiohttp
import aiofiles
import math
import html
from pathlib import Path
from typing import Optional
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from pyrogram.enums import ParseMode as SmartParseMode
from moviepy import VideoFileClip
from bot import dp, SmartPyro
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.pgbar import progress_bar
from bot.helpers.defend import SmartDefender
from config import A360APIBASEURL

logger = LOGGER

class Config:
    TEMP_DIR = Path("./downloads")
    MAX_DURATION = 7200
    MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024
Config.TEMP_DIR.mkdir(exist_ok=True)

def parse_duration_to_seconds(duration_str: str) -> int:
    try:
        parts = duration_str.split(':')
        if len(parts) == 3:
            hours, minutes, seconds = map(int, parts)
            return hours * 3600 + minutes * 60 + seconds
        elif len(parts) == 2:
            minutes, seconds = map(int, parts)
            return minutes * 60 + seconds
        elif len(parts) == 1:
            return int(parts[0])
        return 0
    except:
        return 0

def format_duration(seconds: int) -> str:
    if seconds == 0:
        return "0s"
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    elif minutes:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

def format_size(size_bytes: int) -> str:
    if size_bytes == 0:
        return "0B"
    units = ("B", "KB", "MB", "GB")
    i = int(math.log(size_bytes, 1024)) if size_bytes > 0 else 0
    return f"{round(size_bytes / (1024 ** i), 2)} {units[i]}"

def get_video_duration_moviepy(video_path: str) -> int:
    try:
        clip = VideoFileClip(video_path)
        duration = int(clip.duration)
        clip.close()
        return duration
    except Exception as e:
        logger.error(f"Error getting video duration with moviepy: {e}")
        return 0

class TwitterDownloader:
    async def sanitize_filename(self, title: str) -> str:
        title = re.sub(r'[<>:"/\\|?*]', '', title[:100]).strip()
        sanitized = re.sub(r'\s+', '_', title)
        return f"{sanitized}_{int(time.time())}"

    async def download_file(self, session: aiohttp.ClientSession, url: str, dest: Path, bot: Bot) -> None:
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    logger.info(f"Downloading file from {url} to {dest}")
                    async with aiofiles.open(dest, mode='wb') as f:
                        async for chunk in response.content.iter_chunked(1024 * 1024):
                            await f.write(chunk)
                    logger.info(f"File downloaded successfully to {dest}")
                else:
                    logger.error(f"Failed to download file: HTTP status {response.status}")
                    raise Exception(f"Failed to download file: {response.status}")
        except Exception as e:
            logger.error(f"Error downloading file from {url}: {e}")
            await Smart_Notify(bot, f"{BotCommands}twit", e, None)
            raise

    async def download_video(self, url: str, downloading_message: Message, bot: Bot) -> Optional[dict]:
        api_url = f"{A360APIBASEURL}/thrd/twit?url={url}"
        try:
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(limit_per_host=10),
                timeout=aiohttp.ClientTimeout(total=60)
            ) as session:
                async with session.get(api_url) as response:
                    logger.info(f"API request to {api_url} returned status {response.status}")
                    if response.status != 200:
                        await downloading_message.edit_text("<b>API Error or Video Not Available</b>", parse_mode=ParseMode.HTML)
                        return None
                    data = await response.json()
                    
                    results = data.get("results")
                    if not results:
                        await downloading_message.edit_text("<b>No Results Found</b>", parse_mode=ParseMode.HTML)
                        return None
                    
                    logger.info(f"API response received: {results.get('title', 'No title')}")

                    title = results.get("title", "Twitter Video")
                    safe_title = await self.sanitize_filename(title)

                    video_url = results.get("audio")
                    if not video_url:
                        videos_list = results.get("videos", [])
                        if videos_list and len(videos_list) > 0:
                            video_url = videos_list[0]
                        else:
                            await downloading_message.edit_text("<b>No Video Link Found</b>", parse_mode=ParseMode.HTML)
                            return None

                    await downloading_message.edit_text("<b>Found ☑️ Downloading...</b>", parse_mode=ParseMode.HTML)

                    video_filename = Config.TEMP_DIR / f"{safe_title}.mp4"
                    await self.download_file(session, video_url, video_filename, bot)

                    file_size = os.path.getsize(video_filename)
                    if file_size > Config.MAX_FILE_SIZE:
                        await downloading_message.edit_text("<b>Sorry Bro Video Is Over 2GB</b>", parse_mode=ParseMode.HTML)
                        clean_download(str(video_filename))
                        return None

                    thumbnail_url = results.get("thumbnail")
                    thumbnail_filename = None
                    if thumbnail_url:
                        thumbnail_filename = Config.TEMP_DIR / f"{safe_title}_thumb.jpg"
                        try:
                            await self.download_file(session, thumbnail_url, thumbnail_filename, bot)
                        except Exception as e:
                            logger.warning(f"Thumbnail download failed: {e}")
                            thumbnail_filename = None

                    duration_str = results.get("duration", "0")
                    duration_seconds = parse_duration_to_seconds(duration_str)

                    if duration_seconds == 0:
                        duration_seconds = await asyncio.get_event_loop().run_in_executor(
                            None, get_video_duration_moviepy, str(video_filename)
                        )

                    if duration_seconds > Config.MAX_DURATION:
                        await downloading_message.edit_text("<b>Sorry Bro Video Is Over 2hrs</b>", parse_mode=ParseMode.HTML)
                        clean_download(str(video_filename))
                        if thumbnail_filename:
                            clean_download(str(thumbnail_filename))
                        return None

                    formatted_duration = format_duration(duration_seconds) if duration_seconds > 0 else "Unknown"

                    tweet_url = results.get("tweet_url", url)

                    return {
                        'title': title,
                        'filename': str(video_filename),
                        'thumbnail': str(thumbnail_filename) if thumbnail_filename else None,
                        'webpage_url': tweet_url,
                        'duration_seconds': duration_seconds,
                        'duration_str': formatted_duration,
                        'file_size': format_size(file_size)
                    }
        except Exception as e:
            logger.error(f"Twitter download error: {e}")
            await Smart_Notify(bot, f"{BotCommands}twit", e, downloading_message)
            await downloading_message.edit_text("<b>Twitter Downloader API Dead</b>", parse_mode=ParseMode.HTML)
            return None

async def twit_handler(message: Message, bot: Bot):
    twitter_downloader = TwitterDownloader()
    user_id = message.from_user.id if message.from_user else None
    logger.info(f"Twitter command received, user: {user_id or 'unknown'}, chat: {message.chat.id}")

    url = None
    if message.reply_to_message and message.reply_to_message.text:
        match = re.search(r"https?://(twitter\.com|x\.com|mobile\.twitter\.com|m\.twitter\.com)/\S+", message.reply_to_message.text)
        if match:
            url = match.group(0)
    if not url:
        args = get_args(message)
        if args:
            match = re.search(r"https?://(twitter\.com|x\.com|mobile\.twitter\.com|m\.twitter\.com)/\S+", args[0])
            if match:
                url = match.group(0)

    if not url:
        await send_message(
            chat_id=message.chat.id,
            text="<b>Please provide a valid Twitter/X video link</b>",
            parse_mode=ParseMode.HTML
        )
        return

    logger.info(f"Processing Twitter URL: {url}")

    downloading_message = await send_message(
        chat_id=message.chat.id,
        text="<b>Searching The Video</b>",
        parse_mode=ParseMode.HTML
    )

    try:
        video_info = await twitter_downloader.download_video(url, downloading_message, bot)
        if not video_info:
            await downloading_message.edit_text("<b>Invalid Video URL or Video is Private</b>", parse_mode=ParseMode.HTML)
            return

        title = video_info['title']
        filename = video_info['filename']
        thumbnail = video_info['thumbnail']
        webpage_url = video_info['webpage_url']
        duration_str = video_info['duration_str']
        duration_seconds = video_info['duration_seconds']

        if message.from_user:
            first_name = html.escape(message.from_user.first_name)
            last_name = html.escape(message.from_user.last_name) if message.from_user.last_name else ''
            last_name_part = ' ' + last_name if last_name else ''
            user_link = f"tg://user?id={message.from_user.id}"
            user_info = f"<a href=\"{user_link}\">{first_name}{last_name_part}</a>"
        else:
            user_info = html.escape(message.chat.title)

        escaped_title = html.escape(title)

        caption = (
            f"🐦 <b>Title:</b> {escaped_title}\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>🔗 Url:</b> <a href=\"{webpage_url}\">Watch On Twitter</a>\n"
            f"<b>⏱️ Duration:</b> {duration_str}\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>Downloaded By</b> {user_info}"
        )

        start_time = time.time()
        last_update_time = [start_time]

        send_video_params = {
            'chat_id': message.chat.id,
            'video': filename,
            'supports_streaming': True,
            'caption': caption,
            'parse_mode': SmartParseMode.HTML,
            'width': 1280,
            'height': 720,
            'progress': progress_bar,
            'progress_args': (downloading_message, start_time, last_update_time)
        }

        if duration_seconds > 0:
            send_video_params['duration'] = int(duration_seconds)

        if thumbnail:
            send_video_params['thumb'] = thumbnail

        await SmartPyro.send_video(**send_video_params)
        await delete_messages(message.chat.id, [downloading_message.message_id])

        clean_download(filename)
        logger.info(f"Deleted video file: {filename}")
        if thumbnail:
            clean_download(thumbnail)
            logger.info(f"Deleted thumbnail file: {thumbnail}")

    except Exception as e:
        logger.error(f"Error sending Twitter video: {e}")
        await Smart_Notify(bot, f"{BotCommands}twit", e, downloading_message)
        await downloading_message.edit_text("<b>Twitter Downloader API Dead</b>", parse_mode=ParseMode.HTML)
        if 'filename' in locals() and os.path.exists(filename):
            clean_download(filename)
        if 'thumbnail' in locals() and thumbnail and os.path.exists(thumbnail):
            clean_download(thumbnail)

@dp.message(Command(commands=["twit", "tx", "x"], prefix=BotCommands))
@new_task
@SmartDefender
async def twit_command(message: Message, bot: Bot):
    await twit_handler(message, bot)