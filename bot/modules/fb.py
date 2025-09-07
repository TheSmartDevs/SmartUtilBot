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
from bot.helpers.pgbar import progress_bar
from bot.helpers.defend import SmartDefender
from config import A360APIBASEURL

logger = LOGGER

class Config:
    TEMP_DIR = Path("./downloads")
Config.TEMP_DIR.mkdir(exist_ok=True)

class FacebookDownloader:
    async def sanitize_filename(self, title: str) -> str:
        title = re.sub(r'[<>:"/\\|?*]', '', title[:50]).strip()
        return f"{title.replace(' ', '_')}_{int(time.time())}"
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
            await Smart_Notify(bot, f"{BotCommands}fb", e, None)
            raise
            
    async def download_video(self, url: str, downloading_message: Message, bot: Bot) -> Optional[dict]:
        api_url = f"{A360APIBASEURL}/fb/dl?url={url}"
        try:
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(limit_per_host=10),
                timeout=aiohttp.ClientTimeout(total=30)
            ) as session:
                async with session.get(api_url) as response:
                    logger.info(f"API request to {api_url} returned status {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"API response: {data}")
                        video_url = next(
                            (link["url"] for link in data.get("links", []) if link.get("quality") == "HD"),
                            None
                        )
                        if not video_url:
                            logger.error("No HD video URL found in API response")
                            await downloading_message.edit_text("<b>Unable To Extract Video URL</b>", parse_mode=ParseMode.HTML)
                            return None
                        await downloading_message.edit_text("<b>Found ☑️ Downloading...</b>", parse_mode=ParseMode.HTML)
                        title = data.get("title", "Facebook Video")
                        safe_title = await self.sanitize_filename(title)
                        video_filename = Config.TEMP_DIR / f"{safe_title}.mp4"
                        await self.download_file(session, video_url, video_filename, bot)
                        thumbnail_url = data.get("thumbnail")
                        thumbnail_filename = None
                        if thumbnail_url:
                            thumbnail_filename = Config.TEMP_DIR / f"{safe_title}_thumb.jpg"
                            try:
                                await self.download_file(session, thumbnail_url, thumbnail_filename, bot)
                            except Exception as e:
                                logger.warning(f"Failed to download thumbnail: {e}")
                                thumbnail_filename = None
                        return {
                            'title': title,
                            'filename': str(video_filename),
                            'thumbnail': str(thumbnail_filename) if thumbnail_filename else None,
                            'webpage_url': url
                        }
                    logger.error(f"API request failed: HTTP status {response.status}")
                    return None
        except aiohttp.ClientError as e:
            logger.error(f"Facebook download error: {e}")
            await Smart_Notify(bot, f"{BotCommands}fb", e, downloading_message)
            return None
        except asyncio.TimeoutError:
            logger.error("Request to Facebook API timed out")
            await Smart_Notify(bot, f"{BotCommands}fb", asyncio.TimeoutError("Request to Facebook API timed out"), downloading_message)
            return None
        except Exception as e:
            logger.error(f"Facebook download error: {e}")
            await Smart_Notify(bot, f"{BotCommands}fb", e, downloading_message)
            return None
            
async def fb_handler(message: Message, bot: Bot):
    fb_downloader = FacebookDownloader()
    user_id = message.from_user.id if message.from_user else None
    logger.info(f"Facebook command received, user: {user_id or 'unknown'}, chat: {message.chat.id}, text: {message.text}")
    url = None
    if message.reply_to_message and message.reply_to_message.text:
        match = re.search(r"https?://(www\.facebook\.com|fb\.watch|m\.facebook\.com)/\S+", message.reply_to_message.text)
        if match:
            url = match.group(0)
    if not url:
        args = get_args(message)
        if args:
            match = re.search(r"https?://(www\.facebook\.com|fb\.watch|m\.facebook\.com)/\S+", args[0])
            if match:
                url = match.group(0)
    if not url:
        await send_message(
            chat_id=message.chat.id,
            text="<b>Please provide a valid Facebook video link</b>",
            parse_mode=ParseMode.HTML
        )
        logger.warning(f"No Facebook URL provided, user: {user_id or 'unknown'}, chat: {message.chat.id}")
        return
    logger.info(f"Facebook URL received: {url}, user: {user_id or 'unknown'}, chat: {message.chat.id}")
    downloading_message = await send_message(
        chat_id=message.chat.id,
        text="<b>Searching The Video</b>",
        parse_mode=ParseMode.HTML
    )
    try:
        video_info = await fb_downloader.download_video(url, downloading_message, bot)
        if not video_info:
            await downloading_message.edit_text("<b>Invalid Video URL or Video is Private</b>", parse_mode=ParseMode.HTML)
            logger.error(f"Failed to download video for URL: {url}")
            return
        title = video_info['title']
        filename = video_info['filename']
        thumbnail = video_info['thumbnail']
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
            f"📹 <b>Title:</b> <code>{title}</code>\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>🔗 Url:</b> <a href=\"{webpage_url}\">Watch On Facebook</a>\n"
            f"<b>⏱️ Duration:</b> {duration_str}\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>Downloaded By</b> {user_info}"
        )
        async with aiofiles.open(filename, 'rb'):
            start_time = time.time()
            last_update_time = [start_time]
            send_video_params = {
                'chat_id': message.chat.id,
                'video': filename,
                'supports_streaming': True,
                'caption': caption,
                'parse_mode': SmartParseMode.HTML,
                'duration': int(duration),
                'width': 1280,
                'height': 720,
                'progress': progress_bar,
                'progress_args': (downloading_message, start_time, last_update_time)
            }
            if thumbnail:
                send_video_params['thumb'] = thumbnail
            await SmartPyro.send_video(**send_video_params)
        await delete_messages(message.chat.id, [downloading_message.message_id])
        if os.path.exists(filename):
            clean_download(filename)
            logger.info(f"Deleted video file: {filename}")
        if thumbnail and os.path.exists(thumbnail):
            clean_download(thumbnail)
            logger.info(f"Deleted thumbnail file: {thumbnail}")
    except Exception as e:
        logger.error(f"Error processing Facebook video: {e}")
        await Smart_Notify(bot, f"{BotCommands}fb", e, downloading_message)
        await downloading_message.edit_text("<b>Facebook Downloader API Dead</b>", parse_mode=ParseMode.HTML)
        if 'filename' in locals() and os.path.exists(filename):
            clean_download(filename)
            logger.info(f"Deleted video file on error: {filename}")
        if 'thumbnail' in locals() and thumbnail and os.path.exists(thumbnail):
            clean_download(thumbnail)
            logger.info(f"Deleted thumbnail file on error: {thumbnail}")
            
@dp.message(Command(commands=["fb"], prefix=BotCommands))
@new_task
@SmartDefender
async def fb_command(message: Message, bot: Bot):
    await fb_handler(message, bot)