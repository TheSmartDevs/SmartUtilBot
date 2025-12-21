import os
import re
import time
import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from typing import Optional
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest
from pyrogram.types import InputMediaPhoto, InputMediaVideo
from pyrogram.enums import ParseMode as SmartParseMode
from bot import dp, SmartPyro
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.defend import SmartDefender
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

    async def download_file(self, session: aiohttp.ClientSession, url: str, dest: Path, retries: int = Config.DOWNLOAD_RETRIES) -> Path:
        for attempt in range(1, retries + 1):
            try:
                async with session.get(url) as response:
                    if response.status == 200:
                        async with aiofiles.open(dest, mode='wb') as f:
                            async for chunk in response.content.iter_chunked(1024 * 1024):
                                await f.write(chunk)
                        return dest
                    else:
                        if attempt == retries:
                            raise Exception(f"Failed to download {url}: Status {response.status}")
            except aiohttp.ClientError as e:
                if attempt == retries:
                    raise Exception(f"Error downloading file from {url}: {e}")
            except Exception as e:
                if attempt == retries:
                    raise Exception(f"Unexpected error downloading file from {url}: {e}")
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
                    if response.status != 200:
                        return None
                    
                    data = await response.json()
                    
                    if data.get("status") != "success":
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
                    
                    shortcode = url.split('/')[-2] if '/p/' in url or '/reel/' in url else 'unknown'
                    
                    for index, media in enumerate(data["results"], start=1):
                        media_type = "video" if media["label"].startswith("video") else "image"
                        filename = self.temp_dir / await self.sanitize_filename(shortcode, index, media_type)
                        tasks.append(self.download_file(session, media["download"], filename))
                        
                        thumbnail_url = media.get("thumbnail")
                        if thumbnail_url:
                            thumbnail_filename = self.temp_dir / f"{filename.stem}_thumb.jpg"
                            thumbnail_tasks.append(self.download_file(session, thumbnail_url, thumbnail_filename))
                            thumbnail_paths.append(thumbnail_filename)
                        else:
                            thumbnail_tasks.append(None)
                            thumbnail_paths.append(None)
                    
                    downloaded_files = await asyncio.gather(*tasks, return_exceptions=True)
                    downloaded_thumbnails = await asyncio.gather(*[t for t in thumbnail_tasks if t is not None], return_exceptions=True)
                    thumb_index = 0
                    
                    for index, result in enumerate(downloaded_files):
                        if isinstance(result, Exception):
                            if thumbnail_paths[index] and thumbnail_paths[index].exists():
                                clean_download(thumbnail_paths[index])
                            continue
                        
                        thumbnail_filename = None
                        if thumbnail_tasks[index] is not None:
                            thumb_result = downloaded_thumbnails[thumb_index]
                            if not isinstance(thumb_result, Exception):
                                thumbnail_filename = str(thumbnail_paths[index])
                            thumb_index += 1
                        
                        media_files.append({
                            "filename": str(result),
                            "type": "video" if data["results"][index]["label"].startswith("video") else "image",
                            "thumbnail": thumbnail_filename
                        })
                    
                    if not media_files:
                        return None
                    
                    post_type = "carousel" if data.get("media_count", 1) > 1 else ("video" if any(m["label"].startswith("video") for m in data["results"]) else "image")
                    
                    return {
                        "media_files": media_files,
                        "webpage_url": url,
                        "type": post_type
                    }
        
        except Exception as e:
            LOGGER.error(f"Instagram download error: {e}")
            return None

@dp.message(Command(commands=["in", "insta", "ig"], prefix=BotCommands))
@new_task
@SmartDefender
async def insta_handler(message: Message, bot: Bot):
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
            return
        
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
            return
        
        media_files = content_info["media_files"]
        content_type = content_info["type"]
        
        if content_type in ["carousel", "image"]:
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
                            media_group.append(
                                InputMediaVideo(
                                    media=media["filename"],
                                    thumb=media["thumbnail"] if media["thumbnail"] else None,
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
                    await SmartPyro.send_video(
                        chat_id=message.chat.id,
                        video=media["filename"],
                        thumb=media["thumbnail"] if media["thumbnail"] else None,
                        supports_streaming=True
                    )
                else:
                    await SmartPyro.send_photo(
                        chat_id=message.chat.id,
                        photo=media["filename"]
                    )
            
            await delete_messages(message.chat.id, progress_message.message_id)
            
        except Exception as e:
            LOGGER.error(f"Error uploading Instagram content: {str(e)}")
            await Smart_Notify(bot, "insta", e, message)
            try:
                await progress_message.edit_text(
                    text="<b>❌ Sorry, failed to upload media</b>",
                    parse_mode=SmartParseMode.HTML
                )
            except TelegramBadRequest:
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Sorry, failed to upload media</b>",
                    parse_mode=SmartParseMode.HTML
                )
        
        finally:
            for media in media_files:
                clean_download(media["filename"])
                if media.get("thumbnail"):
                    clean_download(media["thumbnail"])
    
    except Exception as e:
        LOGGER.error(f"Error processing Instagram command: {str(e)}")
        await Smart_Notify(bot, "insta", e, message)
        
        if progress_message:
            try:
                await progress_message.edit_text(
                    text="<b>❌ Sorry, failed to process Instagram URL</b>",
                    parse_mode=SmartParseMode.HTML
                )
            except TelegramBadRequest:
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Sorry, failed to process Instagram URL</b>",
                    parse_mode=SmartParseMode.HTML
                )
        else:
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Sorry, failed to process Instagram URL</b>",
                parse_mode=SmartParseMode.HTML
            )