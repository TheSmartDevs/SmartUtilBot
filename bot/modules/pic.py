import os
import re
import time
import random
import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from typing import Optional
from io import BytesIO
from PIL import Image
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest
from pyrogram.enums import ParseMode as SmartParseMode
from bot import dp, SmartPyro
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.defend import SmartDefender
from config import A360APIBASEURL


async def upscale_image(buffer: bytes, width: int, height: int) -> tuple:
    try:
        random_number = random.randint(1_000_000, 999_999_999_999)
        form_data = aiohttp.FormData()
        form_data.add_field("image_file", buffer, filename="image.jpg", content_type="image/jpeg")
        form_data.add_field("name", str(random_number))
        form_data.add_field("desiredHeight", str(height * 4))
        form_data.add_field("desiredWidth", str(width * 4))
        form_data.add_field("outputFormat", "png")
        form_data.add_field("compressionLevel", "high")
        form_data.add_field("anime", "false")
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://upscalepics.com",
            "Referer": "https://upscalepics.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post("https://api.upscalepics.com/upscale-to-size", data=form_data, headers=headers) as response:
                if response.status == 200:
                    json_response = await response.json()
                    return json_response.get("bgRemoved", "").strip(), None
                else:
                    return None, f"API request failed with status {response.status}"
    except Exception as e:
        return None, f"Upscale error: {str(e)}"


class FacebookDownloader:
    def __init__(self, temp_dir: Path):
        self.temp_dir = temp_dir

    async def sanitize_filename(self, user_id: int, chat_id: int, photo_type: str) -> str:
        return f"{photo_type}_{user_id}_{chat_id}_{int(time.time())}.jpg"

    async def download_file(self, session: aiohttp.ClientSession, url: str, dest: Path, retries: int = 3) -> Path:
        for attempt in range(1, retries + 1):
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        async with aiofiles.open(dest, mode='wb') as f:
                            async for chunk in response.content.iter_chunked(1024 * 1024):
                                await f.write(chunk)
                        LOGGER.info(f"Successfully downloaded: {dest}")
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
            await asyncio.sleep(2)
        raise Exception(f"Failed to download {url} after {retries} attempts")

    async def download_and_upscale_profile(self, fb_url: str, user_id: int, chat_id: int) -> Optional[dict]:
        self.temp_dir.mkdir(exist_ok=True)
        api_url = f"{A360APIBASEURL}/pfp/all?url={fb_url}"
        temp_files = []
        
        try:
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(limit=100),
                timeout=aiohttp.ClientTimeout(total=30)
            ) as session:
                LOGGER.info(f"Sending API request to: {api_url}")
                
                async with session.get(api_url) as response:
                    if response.status != 200:
                        LOGGER.error(f"API request failed with status {response.status}")
                        return None
                    
                    data = await response.json()
                    LOGGER.info(f"API Response: {data}")
                    
                    if not data.get('success'):
                        LOGGER.error("API returned success=false")
                        return None
                    
                    profile_photo_url = data.get('profile_picture', {}).get('hd')
                    
                    if not profile_photo_url:
                        LOGGER.error("No HD profile picture found in API response")
                        return None
                    
                    temp_filename = self.temp_dir / await self.sanitize_filename(user_id, chat_id, "profile_temp")
                    
                    downloaded_file = await self.download_file(session, profile_photo_url, temp_filename)
                    temp_files.append(str(temp_filename))
                    
                    with open(temp_filename, 'rb') as f:
                        image_buffer = f.read()
                    
                    with Image.open(BytesIO(image_buffer)) as img:
                        width, height = img.size
                    
                    LOGGER.info(f"Original image size: {width}x{height}")
                    
                    upscaled_url, error = await upscale_image(image_buffer, width, height)
                    
                    clean_download(*temp_files)
                    
                    if upscaled_url and upscaled_url.startswith("http"):
                        LOGGER.info(f"Upscaled image URL: {upscaled_url}")
                        
                        async with session.get(upscaled_url) as img_resp:
                            if img_resp.status == 200:
                                img_bytes = await img_resp.read()
                                if not img_bytes:
                                    raise ValueError("Empty image data received from upscaler API")
                                
                                final_filename = self.temp_dir / f"profile_{user_id}_{chat_id}_{int(time.time())}.png"
                                with open(final_filename, 'wb') as f:
                                    f.write(img_bytes)
                                
                                LOGGER.info(f"Successfully saved upscaled image: {final_filename}")
                                return {"filename": str(final_filename)}
                            else:
                                LOGGER.error(f"Failed to download upscaled image: Status {img_resp.status}")
                                return None
                    else:
                        LOGGER.error(f"Upscale failed: {error}")
                        return None
        
        except Exception as e:
            LOGGER.error(f"Facebook download and upscale error: {e}")
            clean_download(*temp_files)
            return None


def extract_facebook_url(text: str) -> Optional[str]:
    if not text:
        return None
    fb_patterns = [
        r'(?:https?://)?(?:www\.)?facebook\.com/[^\s]+',
        r'(?:https?://)?(?:www\.)?fb\.com/[^\s]+',
        r'(?:https?://)?(?:m\.)?facebook\.com/[^\s]+',
    ]
    for pattern in fb_patterns:
        match = re.search(pattern, text)
        if match:
            url = match.group(0)
            if not url.startswith('http'):
                url = 'https://' + url
            return url
    return None


@dp.message(Command(commands=["pic"], prefix=BotCommands))
@new_task
@SmartDefender
async def pic_handler(message: Message, bot: Bot):
    LOGGER.info(f"Received command: '{message.text}' from user {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
    progress_message = None
    temp_dir = Path("./downloads")
    temp_dir.mkdir(exist_ok=True)
    profile_filename = None
    
    try:
        fb_url = None
        
        if message.reply_to_message and message.reply_to_message.text:
            fb_url = extract_facebook_url(message.reply_to_message.text)
            LOGGER.info(f"Extracted URL from replied message: {fb_url}")
        else:
            user_input = message.text.split(maxsplit=1)
            if len(user_input) > 1:
                fb_url = extract_facebook_url(user_input[1])
                LOGGER.info(f"Extracted URL from command: {fb_url}")
        
        if not fb_url:
            await send_message(
                chat_id=message.chat.id,
                text="<b>🔗 Send a Facebook profile link.</b>",
                parse_mode=SmartParseMode.HTML
            )
            LOGGER.info(f"No Facebook URL provided in chat {message.chat.id}")
            return
        
        progress_message = await send_message(
            chat_id=message.chat.id,
            text="<b>Fetching Target Profile Pictures...⬇️</b>",
            parse_mode=SmartParseMode.HTML
        )
        
        fb_downloader = FacebookDownloader(temp_dir)
        content_info = await fb_downloader.download_and_upscale_profile(fb_url, message.from_user.id, message.chat.id)
        
        if not content_info:
            await delete_messages(message.chat.id, progress_message.message_id)
            await send_message(
                chat_id=message.chat.id,
                text="<b>Sorry Failed Get Profile Database</b>",
                parse_mode=SmartParseMode.HTML
            )
            return
        
        profile_filename = content_info["filename"]
        
        try:
            await SmartPyro.send_document(
                chat_id=message.chat.id,
                document=profile_filename
            )
            LOGGER.info(f"Successfully sent upscaled profile picture as document to chat {message.chat.id}")
            
            await delete_messages(message.chat.id, progress_message.message_id)
            LOGGER.info(f"Successfully completed pic command for chat {message.chat.id}")
            
        except Exception as e:
            LOGGER.error(f"Error uploading Facebook profile picture: {str(e)}")
            await Smart_Notify(bot, "pic", e, message)
            try:
                await progress_message.edit_text(
                    text="<b>Sorry Failed Get Profile Database</b>",
                    parse_mode=SmartParseMode.HTML
                )
            except TelegramBadRequest:
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>Sorry Failed Get Profile Database</b>",
                    parse_mode=SmartParseMode.HTML
                )
        
        finally:
            if profile_filename:
                clean_download(profile_filename)
    
    except Exception as e:
        LOGGER.error(f"Exception in pic_handler for chat {message.chat.id}: {str(e)}")
        await Smart_Notify(bot, "pic", e, message)
        
        if progress_message:
            try:
                await progress_message.edit_text(
                    text="<b>Sorry Failed Get Profile Database</b>",
                    parse_mode=SmartParseMode.HTML
                )
                LOGGER.info(f"Edited progress message with error in chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                await Smart_Notify(bot, "pic", edit_e, message)
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>Sorry Failed Get Profile Database</b>",
                    parse_mode=SmartParseMode.HTML
                )
                LOGGER.info(f"Sent error message to chat {message.chat.id}")
        else:
            await send_message(
                chat_id=message.chat.id,
                text="<b>Sorry Failed Get Profile Database</b>",
                parse_mode=SmartParseMode.HTML
            )
            LOGGER.info(f"Sent error message to chat {message.chat.id}")
        
        if profile_filename:
            clean_download(profile_filename)