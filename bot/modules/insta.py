# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
#  Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
import os
import re
import time
import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from typing import Optional, List
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest
from pyrogram.types import InputMediaPhoto, InputMediaVideo
from pyrogram.enums import ParseMode as SmartParseMode
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

class Config:
    TEMP_DIR = Path("./downloads")
    MAX_MEDIA_PER_GROUP = 10
    DOWNLOAD_RETRIES = 3
    RETRY_DELAY = 2

Config.TEMP_DIR.mkdir(exist_ok=True)

class InstagramDownloader:
    def __init__(self, temp_dir: Path):
        self.temp_dir = temp_dir

    async def sanitize_filename(self, shortcode: str, index: int, media_type: str) -> str:
        safe_shortcode = re.sub(r'[<>:"/\\|?*]', '', shortcode[:30]).strip()
        return f"{safe_shortcode}_{index}_{int(time.time())}.{'mp4' if media_type == 'video' else 'jpg'}"

    async def sanitize_caption(self, caption: str) -> str:
        if not caption or caption.lower() == "unknown":
            return "Instagram Content"
        sanitized = re.sub(r'@\w+', '', caption).strip()
        return sanitized if sanitized else "Instagram Content"

    async def download_file(self, session: aiohttp.ClientSession, url: str, dest: Path, retries: int = Config.DOWNLOAD_RETRIES) -> Path:
        for attempt in range(1, retries + 1):
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        LOGGER.info(f"Downloading file from {url} to {dest} (attempt {attempt}/{retries})")
                        async with aiofiles.open(dest, mode='wb') as f:
                            async for chunk in response.content.iter_chunked(1024 * 1024):
                                await f.write(chunk)
                        LOGGER.info(f"File downloaded successfully to {dest}")
                        return dest
                    else:
                        error_msg = f"Failed to download {url}: Status {response.status}"
                        LOGGER.error(error_msg)
                        if attempt == retries:
                            raise Exception(error_msg)
            except aiohttp.ClientError as e:
                error_msg = f"Error downloading file from {url}: {e}"
                LOGGER.error(error_msg)
                if attempt == retries:
                    raise Exception(error_msg)
            except Exception as e:
                error_msg = f"Unexpected error downloading file from {url}: {e}"
                LOGGER.error(error_msg)
                if attempt == retries:
                    raise Exception(error_msg)
            
            LOGGER.info(f"Retrying download for {url} in {Config.RETRY_DELAY} seconds...")
            await asyncio.sleep(Config.RETRY_DELAY)
        
        raise Exception(f"Failed to download {url} after {retries} attempts")

    async def download_content(self, url: str, downloading_message: Message, content_type: str) -> Optional[dict]:
        self.temp_dir.mkdir(exist_ok=True)
        api_url = f"{A360APIBASEURL}/insta/dl?url={url}"
        
        try:
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(limit=100),
                timeout=aiohttp.ClientTimeout(total=30)
            ) as session:
                async with session.get(api_url) as response:
                    LOGGER.info(f"API request to {api_url} returned status {response.status}")
                    if response.status != 200:
                        LOGGER.error(f"API request failed: HTTP status {response.status}")
                        return None
                    
                    data = await response.json()
                    LOGGER.info(f"API response: {data}")
                    
                    if data.get("status") != "success":
                        LOGGER.error("API response indicates failure")
                        return None
                    
                    if content_type in ["reel", "igtv"]:
                        await downloading_message.edit_text(
                            "<b>Found ☑️ Downloading...</b>",
                            parse_mode=SmartParseMode.HTML
                        )
                    
                    media_files = []
                    tasks = []
                    thumbnail_tasks = []
                    thumbnail_paths = []
                    
                    for index, media in enumerate(data["results"]):
                        media_type = media["type"]
                        filename = self.temp_dir / await self.sanitize_filename(url.split('/')[-2], index, media_type)
                        tasks.append(self.download_file(session, media["downloadLink"], filename))
                        
                        thumbnail_url = media.get("thumbnail")
                        if thumbnail_url:
                            thumbnail_filename = self.temp_dir / f"{filename.stem}_thumb.jpg"
                            thumbnail_tasks.append(self.download_file(session, thumbnail_url, thumbnail_filename))
                            thumbnail_paths.append(thumbnail_filename)
                        else:
                            thumbnail_tasks.append(None)
                            thumbnail_paths.append(None)
                    
                    downloaded_files = await asyncio.gather(*tasks, return_exceptions=True)
                    downloaded_thumbnails = await asyncio.gather(*[t for t in thumbnail_tasks if t], return_exceptions=True) if any(t for t in thumbnail_tasks) else [None] * len(tasks)
                    
                    for index, (result, thumbnail_result, thumbnail_path) in enumerate(zip(downloaded_files, thumbnail_tasks, thumbnail_paths)):
                        if isinstance(result, Exception):
                            LOGGER.error(f"Failed to download media {index} for URL {data['results'][index]['downloadLink']}: {result}")
                            if thumbnail_path and os.path.exists(thumbnail_path):
                                clean_download(thumbnail_path)
                                LOGGER.info(f"Deleted orphaned thumbnail: {thumbnail_path}")
                            continue
                        
                        thumbnail_filename = None
                        if thumbnail_result and not isinstance(thumbnail_result, Exception):
                            thumbnail_filename = str(thumbnail_path)
                        
                        media_files.append({
                            "filename": str(result),
                            "type": data["results"][index]["type"],
                            "thumbnail": thumbnail_filename
                        })
                    
                    if not media_files:
                        LOGGER.error("No media files downloaded successfully")
                        return None
                    
                    return {
                        "title": await self.sanitize_caption("Instagram Content"),
                        "media_files": media_files,
                        "webpage_url": url,
                        "type": "carousel" if len(data["results"]) > 1 else data["results"][0]["type"]
                    }
        
        except Exception as e:
            LOGGER.error(f"Instagram download error: {e}")
            return None

@dp.message(Command(commands=["in", "insta", "ig"], prefix=BotCommands))
@new_task
@SmartDefender
async def insta_handler(message: Message, bot: Bot):
    LOGGER.info(f"Received command: '{message.text}' from user {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
    progress_message = None
    
    try:
        url = None
        args = get_args(message)
        
        if args:
            match = re.search(r"https?://(www\.)?instagram\.com/\S+", args[0])
            if match:
                url = match.group(0)
        elif message.reply_to_message and message.reply_to_message.text:
            match = re.search(r"https?://(www\.)?instagram\.com/\S+", message.reply_to_message.text)
            if match:
                url = match.group(0)
        
        if not url:
            progress_message = await send_message(
                chat_id=message.chat.id,
                text="<b>Please provide a valid Instagram URL or reply to a message with one ❌</b>",
                parse_mode=SmartParseMode.HTML
            )
            LOGGER.info(f"No Instagram URL provided in chat {message.chat.id}")
            return
        
        LOGGER.info(f"Instagram URL received: {url}, user: {message.from_user.id or 'unknown'}, chat: {message.chat.id}")
        content_type = "reel" if "/reel/" in url else "igtv" if "/tv/" in url else "story" if "/stories/" in url else "post"
        
        progress_message = await send_message(
            chat_id=message.chat.id,
            text="<b>Searching The Video...</b>" if content_type in ["reel", "igtv"] else "<code>🔍 Fetching media from Instagram...</code>",
            parse_mode=SmartParseMode.HTML
        )
        
        ig_downloader = InstagramDownloader(Config.TEMP_DIR)
        content_info = await ig_downloader.download_content(url, progress_message, content_type)
        
        if not content_info:
            await delete_messages(message.chat.id, progress_message.message_id)
            await send_message(
                chat_id=message.chat.id,
                text="<b>Unable To Extract The URL 😕</b>",
                parse_mode=SmartParseMode.HTML
            )
            LOGGER.error(f"Failed to download content for URL: {url}")
            return
        
        media_files = content_info["media_files"]
        content_type = content_info["type"]
        
        if content_type == "carousel" or media_files[0]["type"] == "image":
            await progress_message.edit_text(
                "<code>📤 Uploading...</code>",
                parse_mode=SmartParseMode.HTML
            )
        
        try:
            if content_type == "carousel" and len(media_files) > 1:
                for i in range(0, len(media_files), Config.MAX_MEDIA_PER_GROUP):
                    media_group = []
                    for media in media_files[i:i + Config.MAX_MEDIA_PER_GROUP]:
                        if media["type"] == "image":
                            media_group.append(
                                InputMediaPhoto(
                                    media=media["filename"]
                                )
                            )
                        else:
                            video_clip = VideoFileClip(media["filename"])
                            duration = video_clip.duration
                            video_clip.close()
                            media_group.append(
                                InputMediaVideo(
                                    media=media["filename"],
                                    thumb=media["thumbnail"] if media["thumbnail"] else None,
                                    duration=int(duration),
                                    supports_streaming=True
                                )
                            )
                    
                    await SmartPyro.send_media_group(
                        chat_id=message.chat.id,
                        media=media_group
                    )
            else:
                media = media_files[0]
                if media["type"] == "video":
                    video_clip = VideoFileClip(media["filename"])
                    duration = video_clip.duration
                    video_clip.close()
                    start_time = time.time()
                    last_update_time = [start_time]
                    await SmartPyro.send_video(
                        chat_id=message.chat.id,
                        video=media["filename"],
                        thumb=media["thumbnail"] if media["thumbnail"] else None,
                        duration=int(duration),
                        supports_streaming=True,
                        progress=progress_bar,
                        progress_args=(progress_message, start_time, last_update_time)
                    )
                else:
                    await SmartPyro.send_photo(
                        chat_id=message.chat.id,
                        photo=media["filename"]
                    )
            
            await delete_messages(message.chat.id, progress_message.message_id)
            LOGGER.info(f"Successfully uploaded {content_type} for URL {url} to chat {message.chat.id}")
            
        except Exception as e:
            LOGGER.error(f"Error uploading Instagram content in chat {message.chat.id}: {str(e)}")
            await Smart_Notify(bot, "insta", e, message)
            try:
                await progress_message.edit_text(
                    text="<b>❌ Sorry, failed to upload media</b>",
                    parse_mode=SmartParseMode.HTML
                )
                LOGGER.info(f"Edited progress message with upload error in chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                await Smart_Notify(bot, "insta", edit_e, message)
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Sorry, failed to upload media</b>",
                    parse_mode=SmartParseMode.HTML
                )
                LOGGER.info(f"Sent upload error message to chat {message.chat.id}")
        
        finally:
            for media in media_files:
                clean_download(media["filename"])
                LOGGER.info(f"Deleted media file: {media['filename']}")
                if media["thumbnail"]:
                    clean_download(media["thumbnail"])
                    LOGGER.info(f"Deleted thumbnail file: {media['thumbnail']}")
    
    except Exception as e:
        LOGGER.error(f"Error processing Instagram command in chat {message.chat.id}: {str(e)}")
        await Smart_Notify(bot, "insta", e, message)
        
        if progress_message:
            try:
                await progress_message.edit_text(
                    text="<b>❌ Sorry, failed to process Instagram URL</b>",
                    parse_mode=SmartParseMode.HTML
                )
                LOGGER.info(f"Edited progress message with error in chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                await Smart_Notify(bot, "insta", edit_e, message)
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Sorry, failed to process Instagram URL</b>",
                    parse_mode=SmartParseMode.HTML
                )
                LOGGER.info(f"Sent error message to chat {message.chat.id}")
        else:
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Sorry, failed to process Instagram URL</b>",
                parse_mode=SmartParseMode.HTML
            )
            LOGGER.info(f"Sent error message to chat {message.chat.id}")