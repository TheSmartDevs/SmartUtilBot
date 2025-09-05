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
from bot import dp, SmartPyro
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.pgbar import progress_bar
from config import A360APIBASEURL

logger = LOGGER

class Config:
    TEMP_DIR = Path("./downloads")

Config.TEMP_DIR.mkdir(exist_ok=True)

class TikTokDownloader:
    async def sanitize_filename(self, title: str) -> str:
        title = re.sub(r'[<>:"/\\|?*]', '', title[:50]).strip()
        return f"{title.replace(' ', '_')}_{int(time.time())}"

    async def download_media(self, url: str, downloading_message: Message, bot: Bot) -> Optional[dict]:
        Config.TEMP_DIR.mkdir(exist_ok=True)
        api_url = f"{A360APIBASEURL}/tik/dl?url={url}"
        try:
            async with aiohttp.ClientSession(
                connector=aiohttp.TCPConnector(limit=100),
                timeout=aiohttp.ClientTimeout(total=30)
            ) as session:
                async with session.get(api_url) as response:
                    logger.info(f"API request to {api_url} returned status {response.status}")
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"API response: {data}")
                        if not data.get("success"):
                            logger.error("API response success is not true")
                            await downloading_message.edit_text("<b>Unable To Extract Media</b>", parse_mode=ParseMode.HTML)
                            return None
                        links = data.get("links", [])
                        title = data.get("title", "TikTok Media")
                        high_quality_video = None
                        audio = None
                        thumbnail = None
                        for item in links:
                            filename = item.get("filename", "")
                            if filename.endswith("_hd.mp4") and not high_quality_video:
                                high_quality_video = item.get("url")
                            elif filename.endswith(".mp4") and not high_quality_video:
                                high_quality_video = item.get("url")
                            elif filename.endswith(".mp3") and not audio:
                                audio = item.get("url")
                        if not high_quality_video and not audio:
                            logger.error("No suitable media found in API response")
                            await downloading_message.edit_text("<b>Unable To Extract Media</b>", parse_mode=ParseMode.HTML)
                            return None
                        await downloading_message.edit_text("<b>Found ☑️ Downloading...</b>", parse_mode=ParseMode.HTML)
                        safe_title = await self.sanitize_filename(title)
                        result = {'title': title, 'webpage_url': url}
                        if high_quality_video:
                            video_filename = Config.TEMP_DIR / f"{safe_title}.mp4"
                            await self._download_file(session, high_quality_video, video_filename, bot)
                            result['video_filename'] = str(video_filename)
                            for item in links:
                                if item.get("filename", "").endswith(".jpg"):
                                    thumbnail = item.get("url")
                                    break
                            if thumbnail:
                                thumbnail_filename = Config.TEMP_DIR / f"{safe_title}_thumb.jpg"
                                await self._download_file(session, thumbnail, thumbnail_filename, bot)
                                result['thumbnail_filename'] = str(thumbnail_filename)
                        elif audio:
                            audio_filename = Config.TEMP_DIR / f"{safe_title}.mp3"
                            await self._download_file(session, audio, audio_filename, bot)
                            result['audio_filename'] = str(audio_filename)
                        return result
                    logger.error(f"API request failed: HTTP status {response.status}")
                    return None
        except aiohttp.ClientError as e:
            logger.error(f"TikTok download error: {e}")
            await Smart_Notify(bot, f"{BotCommands}tik", e, downloading_message)
            return None
        except asyncio.TimeoutError:
            logger.error("Request to TikTok API timed out")
            await Smart_Notify(bot, f"{BotCommands}tik", asyncio.TimeoutError("Request to TikTok API timed out"), downloading_message)
            return None
        except Exception as e:
            logger.error(f"TikTok download error: {e}")
            await Smart_Notify(bot, f"{BotCommands}tik", e, downloading_message)
            return None

    async def _download_file(self, session: aiohttp.ClientSession, url: str, dest: Path, bot: Bot):
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    logger.info(f"Downloading media from {url} to {dest}")
                    async with aiofiles.open(dest, mode='wb') as f:
                        async for chunk in response.content.iter_chunked(1024 * 1024):
                            await f.write(chunk)
                    logger.info(f"Media downloaded successfully to {dest}")
                else:
                    logger.error(f"Failed to download file: HTTP status {response.status}")
                    raise Exception(f"Failed to download file: {response.status}")
        except Exception as e:
            logger.error(f"Error downloading file from {url}: {e}")
            await Smart_Notify(bot, f"{BotCommands}tik", e, None)
            raise

async def tik_handler(message: Message, bot: Bot):
    tik_downloader = TikTokDownloader()
    user_id = message.from_user.id if message.from_user else None
    logger.info(f"TikTok command received, user: {user_id or 'unknown'}, chat: {message.chat.id}, text: {message.text}")
    url = None
    if message.reply_to_message and message.reply_to_message.text:
        match = re.search(r"https?://(vm\.tiktok\.com|www\.tiktok\.com)/\S+", message.reply_to_message.text)
        if match:
            url = match.group(0)
    if not url:
        args = get_args(message)
        if args:
            match = re.search(r"https?://(vm\.tiktok\.com|www\.tiktok\.com)/\S+", args[0])
            if match:
                url = match.group(0)
    if not url:
        await send_message(
            chat_id=message.chat.id,
            text="<b>Please provide a TikTok link</b>",
            parse_mode=ParseMode.HTML
        )
        logger.warning(f"No TikTok URL provided, user: {user_id or 'unknown'}, chat: {message.chat.id}")
        return
    logger.info(f"TikTok URL received: {url}, user: {user_id or 'unknown'}, chat: {message.chat.id}")
    downloading_message = await send_message(
        chat_id=message.chat.id,
        text="<b>Searching The Media</b>",
        parse_mode=ParseMode.HTML
    )
    try:
        media_info = await tik_downloader.download_media(url, downloading_message, bot)
        if not media_info:
            await downloading_message.edit_text("<b>Unable To Extract Media</b>", parse_mode=ParseMode.HTML)
            logger.error(f"Failed to download media for URL: {url}")
            return
        start_time = time.time()
        last_update_time = [start_time]
        user_info = (
            f"<a href=\"tg://user?id={message.from_user.id}\">{message.from_user.first_name}{' ' + message.from_user.last_name if message.from_user.last_name else ''} {'🇧🇩' if message.from_user.language_code == 'bn' else ''}</a>" if message.from_user
            else f"<a href=\"https://t.me/{message.chat.username or 'this group'}\">{message.chat.title}</a>"
        )
        caption = (
            f"🎥 <b>Title:</b> <code>{media_info['title']}</code>\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>🔗 Url:</b> <a href=\"{media_info['webpage_url']}\">Watch On TikTok</a>\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>Downloaded By</b> {user_info}"
        )
        if 'video_filename' in media_info:
            thumbnail = media_info.get('thumbnail_filename')
            async with aiofiles.open(media_info['video_filename'], 'rb'):
                await SmartPyro.send_video(
                    chat_id=message.chat.id,
                    video=media_info['video_filename'],
                    caption=caption,
                    parse_mode=SmartParseMode.HTML,
                    thumb=thumbnail,
                    supports_streaming=True,
                    progress=progress_bar,
                    progress_args=(downloading_message, start_time, last_update_time)
                )
        elif 'audio_filename' in media_info:
            async with aiofiles.open(media_info['audio_filename'], 'rb'):
                await SmartPyro.send_audio(
                    chat_id=message.chat.id,
                    audio=media_info['audio_filename'],
                    caption=caption,
                    parse_mode=SmartParseMode.HTML,
                    title=media_info['title'],
                    progress=progress_bar,
                    progress_args=(downloading_message, start_time, last_update_time)
                )
        await delete_messages(message.chat.id, [downloading_message.message_id])
        for key in ['video_filename', 'thumbnail_filename', 'audio_filename']:
            if key in media_info and os.path.exists(media_info[key]):
                clean_download(media_info[key])
                logger.info(f"Deleted file: {media_info[key]}")
    except Exception as e:
        logger.error(f"Error processing TikTok media: {e}")
        await Smart_Notify(bot, f"{BotCommands}tik", e, downloading_message)
        await downloading_message.edit_text("<b>TikTok Downloader API Dead</b>", parse_mode=ParseMode.HTML)

@dp.message(Command(commands=["tik", "tt"], prefix=BotCommands))
@new_task
async def tik_command(message: Message, bot: Bot):
    await tik_handler(message, bot)