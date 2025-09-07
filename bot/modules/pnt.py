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
from typing import Optional
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest
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
    DOWNLOAD_RETRIES = 3
    RETRY_DELAY = 2

Config.TEMP_DIR.mkdir(exist_ok=True)

class PinterestDownloader:
    def __init__(self, temp_dir: Path):
        self.temp_dir = temp_dir

    async def sanitize_filename(self, title: str) -> str:
        safe_title = re.sub(r'[<>:"/\\|?*]', '', title[:50]).strip()
        return f"{safe_title.replace(' ', '_')}_{int(time.time())}"

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

    async def download_media(self, url: str, downloading_message: Message) -> Optional[dict]:
        self.temp_dir.mkdir(exist_ok=True)
        api_url = f"{A360APIBASEURL}/pnt/dl?url={url}"
        
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
                        LOGGER.error("API response status is not success")
                        return None
                    
                    await downloading_message.edit_text(
                        "<b>Found ☑️ Downloading...</b>",
                        parse_mode=SmartParseMode.HTML
                    )
                    
                    media = data.get("media", [])
                    title = data.get("title", "Pinterest Media")
                    
                    high_quality_video = None
                    thumbnail_url = None
                    image_url = None
                    
                    for item in media:
                        if item.get("type") == "video/mp4" and (not high_quality_video or "720p" in item.get("quality", "")):
                            high_quality_video = item.get("url")
                        elif item.get("type") == "image/jpeg":
                            if item.get("quality") == "Thumbnail":
                                thumbnail_url = item.get("url")
                            else:
                                image_url = item.get("url")
                    
                    if not high_quality_video and not image_url and not thumbnail_url:
                        LOGGER.error("No suitable media found in API response")
                        return None
                    
                    safe_title = await self.sanitize_filename(title)
                    result = {
                        'title': title,
                        'webpage_url': url
                    }
                    
                    if high_quality_video:
                        video_filename = self.temp_dir / f"{safe_title}.mp4"
                        await self.download_file(session, high_quality_video, video_filename)
                        result['video_filename'] = str(video_filename)
                        
                        if thumbnail_url:
                            thumbnail_filename = self.temp_dir / f"{safe_title}_thumb.jpg"
                            await self.download_file(session, thumbnail_url, thumbnail_filename)
                            result['thumbnail_filename'] = str(thumbnail_filename)
                    
                    elif image_url:
                        image_filename = self.temp_dir / f"{safe_title}.jpg"
                        await self.download_file(session, image_url, image_filename)
                        result['image_filename'] = str(image_filename)
                    
                    elif thumbnail_url:
                        image_filename = self.temp_dir / f"{safe_title}.jpg"
                        await self.download_file(session, thumbnail_url, image_filename)
                        result['image_filename'] = str(image_filename)
                    
                    return result
        
        except Exception as e:
            LOGGER.error(f"Pinterest download error: {e}")
            return None

@dp.message(Command(commands=["pnt", "pint", "pin", "pn"], prefix=BotCommands))
@new_task
@SmartDefender
async def pinterest_handler(message: Message, bot: Bot):
    LOGGER.info(f"Received command: '{message.text}' from user {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
    progress_message = None
    
    try:
        url = None
        args = get_args(message)
        
        if args:
            match = re.search(r"https?://(pin\.it|in\.pinterest\.com|www\.pinterest\.com)/\S+", args[0])
            if match:
                url = match.group(0)
        elif message.reply_to_message and message.reply_to_message.text:
            match = re.search(r"https?://(pin\.it|in\.pinterest\.com|www\.pinterest\.com)/\S+", message.reply_to_message.text)
            if match:
                url = match.group(0)
        
        if not url:
            progress_message = await send_message(
                chat_id=message.chat.id,
                text="<b>Please provide a valid Pinterest URL or reply to a message with one ❌</b>",
                parse_mode=SmartParseMode.HTML
            )
            LOGGER.info(f"No Pinterest URL provided in chat {message.chat.id}")
            return
        
        LOGGER.info(f"Pinterest URL received: {url}, user: {message.from_user.id or 'unknown'}, chat: {message.chat.id}")
        
        progress_message = await send_message(
            chat_id=message.chat.id,
            text="<b>🔍 Searching The Media...</b>",
            parse_mode=SmartParseMode.HTML
        )
        
        pin_downloader = PinterestDownloader(Config.TEMP_DIR)
        media_info = await pin_downloader.download_media(url, progress_message)
        
        if not media_info:
            await delete_messages(message.chat.id, progress_message.message_id)
            await send_message(
                chat_id=message.chat.id,
                text="<b>Unable To Extract The URL 😕</b>",
                parse_mode=SmartParseMode.HTML
            )
            LOGGER.error(f"Failed to download media for URL: {url}")
            return
        
        await progress_message.edit_text(
            "<code>📤 Uploading...</code>",
            parse_mode=SmartParseMode.HTML
        )
        
        try:
            start_time = time.time()
            last_update_time = [start_time]
            
            if 'video_filename' in media_info:
                video_clip = VideoFileClip(media_info['video_filename'])
                duration = video_clip.duration
                video_clip.close()
                
                await SmartPyro.send_video(
                    chat_id=message.chat.id,
                    video=media_info['video_filename'],
                    thumb=media_info.get('thumbnail_filename'),
                    duration=int(duration),
                    supports_streaming=True,
                    progress=progress_bar,
                    progress_args=(progress_message, start_time, last_update_time)
                )
            
            elif 'image_filename' in media_info:
                await SmartPyro.send_photo(
                    chat_id=message.chat.id,
                    photo=media_info['image_filename']
                )
            
            await delete_messages(message.chat.id, progress_message.message_id)
            LOGGER.info(f"Successfully uploaded Pinterest media for URL {url} to chat {message.chat.id}")
            
        except Exception as e:
            LOGGER.error(f"Error uploading Pinterest media in chat {message.chat.id}: {str(e)}")
            await Smart_Notify(bot, "pinterest", e, message)
            try:
                await progress_message.edit_text(
                    text="<b>❌ Sorry, failed to upload media</b>",
                    parse_mode=SmartParseMode.HTML
                )
                LOGGER.info(f"Edited progress message with upload error in chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                await Smart_Notify(bot, "pinterest", edit_e, message)
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Sorry, failed to upload media</b>",
                    parse_mode=SmartParseMode.HTML
                )
                LOGGER.info(f"Sent upload error message to chat {message.chat.id}")
        
        finally:
            for key in ['video_filename', 'thumbnail_filename', 'image_filename']:
                if key in media_info and os.path.exists(media_info[key]):
                    os.remove(media_info[key])
                    LOGGER.info(f"Deleted file: {media_info[key]}")
    
    except Exception as e:
        LOGGER.error(f"Error processing Pinterest command in chat {message.chat.id}: {str(e)}")
        await Smart_Notify(bot, "pinterest", e, message)
        
        if progress_message:
            try:
                await progress_message.edit_text(
                    text="<b>❌ Sorry, failed to process Pinterest URL</b>",
                    parse_mode=SmartParseMode.HTML
                )
                LOGGER.info(f"Edited progress message with error in chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                await Smart_Notify(bot, "pinterest", edit_e, message)
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Sorry, failed to process Pinterest URL</b>",
                    parse_mode=SmartParseMode.HTML
                )
                LOGGER.info(f"Sent error message to chat {message.chat.id}")
        else:
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Sorry, failed to process Pinterest URL</b>",
                parse_mode=SmartParseMode.HTML
            )
            LOGGER.info(f"Sent error message to chat {message.chat.id}")