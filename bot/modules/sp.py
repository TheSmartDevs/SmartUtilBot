import os
import time
import aiohttp
import re
import asyncio
import aiofiles
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from pyrogram import Client
from pyrogram.enums import ParseMode as SmartParseMode
from pyrogram.types import Message as SmartMessage, InlineKeyboardMarkup, InlineKeyboardButton
from typing import Optional
from config import A360APIBASEURL
from bot import dp, SmartPyro
from bot.helpers.commands import BotCommands
from bot.helpers.utils import new_task, clean_download
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.pgbar import progress_bar
from bot.helpers.defend import SmartDefender
from bot.helpers.botutils import send_message, delete_messages
import urllib.parse

logger = LOGGER

class Config:
    TEMP_DIR = Path("./downloads")

Config.TEMP_DIR.mkdir(exist_ok=True)

executor = ThreadPoolExecutor(max_workers=10)

async def sanitize_filename(title: str) -> str:
    title = re.sub(r'[<>:"/\\|?*]', '', title[:50]).strip()
    return f"{title.replace(' ', '_')}_{int(time.time())}"

async def download_image(url: str, output_path: str, bot: Bot) -> Optional[str]:
    logger.info(f"Starting download of image from {url}")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                logger.info(f"HTTP Request: GET {url} \"HTTP/1.1 {response.status} {response.reason}\"")
                if response.status == 200:
                    async with aiofiles.open(output_path, 'wb') as file:
                        await file.write(await response.read())
                    logger.info(f"Image downloaded successfully to {output_path}")
                    return output_path
                else:
                    logger.error(f"Failed to download image: HTTP status {response.status}")
                    await Smart_Notify(bot, f"{BotCommands}sp", Exception(f"Failed to download image: HTTP status {response.status}"), None)
    except Exception as e:
        logger.error(f"Failed to download image: {e}")
        await Smart_Notify(bot, f"{BotCommands}sp", e, None)
    return None

async def handle_spotify_request(message: Message, bot: Bot, input_text: Optional[str]):
    output_filename = None
    cover_path = None
    
    if not input_text and message.reply_to_message and message.reply_to_message.text:
        input_text = message.reply_to_message.text.strip()
    if not input_text:
        await send_message(
            chat_id=message.chat.id,
            text="<b>Please provide a track Spotify URL or name</b>",
            parse_mode=ParseMode.HTML
        )
        logger.warning(f"No input provided, user: {message.from_user.id if message.from_user else 'unknown'}, chat: {message.chat.id}")
        return
    is_url = input_text.lower().startswith('http')
    status = await send_message(
        chat_id=message.chat.id,
        text="<b>Searching The Music</b>",
        parse_mode=ParseMode.HTML
    )
    user_name = f"{message.from_user.first_name}{' ' + message.from_user.last_name if message.from_user.last_name else ''}" if message.from_user else message.chat.title
    user_id = message.from_user.id if message.from_user else message.chat.id
    logger.info(f"Command SP Received: From User {user_name} {user_id}")
    logger.info(f"{user_name} {user_id} Query - {input_text} Type - Audio")
    try:
        async with aiohttp.ClientSession() as session:
            if is_url:
                logger.info(f"Processing Spotify URL: {input_text}")
                api_url = f"{A360APIBASEURL}/sp/dl?url={urllib.parse.quote(input_text)}"
                async with session.get(api_url) as response:
                    logger.info(f"HTTP Request: GET {api_url} \"HTTP/1.1 {response.status} {response.reason}\"")
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Track API response: {data}")
                        if data["status"] == "success":
                            await status.edit_text("<b>Found ☑️ Downloading...</b>", parse_mode=ParseMode.HTML)
                        else:
                            await status.edit_text("<b>Please Provide A Valid Spotify URL ❌</b>", parse_mode=ParseMode.HTML)
                            logger.error(f"Invalid Spotify URL: {input_text}")
                            await Smart_Notify(bot, f"{BotCommands}sp", Exception(f"Invalid Spotify URL: {input_text}"), status)
                            return
                    else:
                        await status.edit_text("<b>❌ Song Not Available On Spotify</b>", parse_mode=ParseMode.HTML)
                        logger.error(f"API request failed: HTTP status {response.status}")
                        await Smart_Notify(bot, f"{BotCommands}sp", Exception(f"API request failed: HTTP status {response.status}"), status)
                        return
            else:
                logger.info(f"Processing Spotify search query: {input_text}")
                encoded_query = urllib.parse.quote(input_text)
                api_url = f"{A360APIBASEURL}/sp/search?q={encoded_query}"
                async with session.get(api_url) as response:
                    logger.info(f"HTTP Request: GET {api_url} \"HTTP/1.1 {response.status} {response.reason}\"")
                    if response.status == 200:
                        data = await response.json()
                        logger.info(f"Search API response: {data}")
                        if data["status"] == "success" and data["results"]:
                            await status.edit_text("<b>Found ☑️ Downloading...</b>", parse_mode=ParseMode.HTML)
                            track = data["results"][0]
                            track_url = track["url"]
                            logger.info(f"Selected track: {track['title']} (URL: {track_url})")
                            track_api_url = f"{A360APIBASEURL}/sp/dl?url={urllib.parse.quote(track_url)}"
                            async with session.get(track_api_url) as track_response:
                                logger.info(f"HTTP Request: GET {track_api_url} \"HTTP/1.1 {track_response.status} {track_response.reason}\"")
                                if track_response.status == 200:
                                    data = await track_response.json()
                                    logger.info(f"Track API response: {data}")
                                    if data["status"] != "success":
                                        await status.edit_text("<b>Song Metadata Unavailable</b>", parse_mode=ParseMode.HTML)
                                        logger.error("Song metadata unavailable")
                                        await Smart_Notify(bot, f"{BotCommands}sp", Exception("Song metadata unavailable"), status)
                                        return
                                else:
                                    await status.edit_text("<b>❌ Song Unavailable Bro Try Later</b>", parse_mode=ParseMode.HTML)
                                    logger.error(f"Track API request failed: HTTP status {track_response.status}")
                                    await Smart_Notify(bot, f"{BotCommands}sp", Exception(f"Track API request failed: HTTP status {track_response.status}"), status)
                                    return
                        else:
                            await status.edit_text("<b>Sorry No Songs Matched To Your Search!</b>", parse_mode=ParseMode.HTML)
                            logger.error(f"No songs matched search query: {input_text}")
                            return
                    else:
                        await status.edit_text("<b>❌ Sorry Bro Spotify Search API Dead</b>", parse_mode=ParseMode.HTML)
                        logger.error(f"Search API request failed: HTTP status {response.status}")
                        await Smart_Notify(bot, f"{BotCommands}sp", Exception(f"Search API request failed: HTTP status {response.status}"), status)
                        return
            
            title = data.get("title", "Unknown")
            artists = data.get("author", "Unknown")
            duration = data.get("duration", "Unknown")
            album = artists
            release_date = "Unknown"
            spotify_url = input_text if is_url else track_url
            download_url = data.get("download_link")
            cover_url = data.get("cover")
            
            if not download_url:
                await status.edit_text("<b>❌ Download link not available</b>", parse_mode=ParseMode.HTML)
                logger.error("Download link not available in API response")
                await Smart_Notify(bot, f"{BotCommands}sp", Exception("Download link not available"), status)
                return
            
            if cover_url:
                Config.TEMP_DIR.mkdir(exist_ok=True)
                cover_path = Config.TEMP_DIR / f"{await sanitize_filename(title)}.jpg"
                downloaded_path = await download_image(cover_url, str(cover_path), bot)
                if downloaded_path:
                    logger.info(f"Cover image downloaded to {downloaded_path}")
                else:
                    logger.warning("Failed to download cover image")
                    cover_path = None
            
            safe_title = await sanitize_filename(title)
            output_filename = Config.TEMP_DIR / f"{safe_title}.mp3"
            logger.info(f"Downloading Spotify Music: {output_filename}")
            async with session.get(download_url) as response:
                logger.info(f"HTTP Request: GET {download_url} \"HTTP/1.1 {response.status} {response.reason}\"")
                if response.status == 200:
                    async with aiofiles.open(output_filename, 'wb') as file:
                        await file.write(await response.read())
                    logger.info(f"Audio file downloaded successfully to {output_filename}")
                else:
                    await status.edit_text("<b>❌ Sorry Bro Spotify DL API Dead</b>", parse_mode=ParseMode.HTML)
                    logger.error(f"Audio download failed: HTTP status {response.status}")
                    await Smart_Notify(bot, f"{BotCommands}sp", Exception(f"Audio download failed: HTTP status {response.status}"), status)
                    logger.info(f"Cleaning Download: {output_filename}")
                    clean_download(output_filename, cover_path)
                    return
            
            user_info = (
                f"<a href=\"tg://user?id={message.from_user.id}\">{user_name}</a>" if message.from_user
                else f"<a href=\"https://t.me/{message.chat.username or 'this group'}\">{message.chat.title}</a>"
            )
            audio_caption = (
                f"🌟 <b>Title</b>: <code>{title}</code>\n"
                f"💥 <b>Artist</b>: <code>{artists}</code>\n"
                f"✨ <b>Duration</b>: <code>{duration}</code>\n"
                f"👀 <b>Album</b>: <code>{album}</code>\n"
                f"🎵 <b>Release Date</b>: <code>{release_date}</code>\n"
                f"<b>━━━━━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>Downloaded By</b> {user_info}"
            )
            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("🎸 Listen On Spotify", url=spotify_url)]
            ])
            last_update_time = [0]
            start_time = time.time()
            logger.info("Starting upload of audio file to Telegram")
            await SmartPyro.send_audio(
                chat_id=message.chat.id,
                audio=str(output_filename),
                caption=audio_caption,
                title=title,
                performer=artists,
                parse_mode=SmartParseMode.HTML,
                thumb=str(cover_path) if cover_path else None,
                reply_markup=reply_markup,
                progress=progress_bar,
                progress_args=(status, start_time, last_update_time)
            )
            logger.info("Upload of audio successfully completed")
            logger.info(f"Cleaning Download: {output_filename}")
            clean_download(output_filename, cover_path)
            await delete_messages(message.chat.id, [status.message_id])
            logger.info("Status message deleted")
    except Exception as e:
        await status.edit_text("<b>❌ Sorry Bro Spotify DL API Dead</b>", parse_mode=ParseMode.HTML)
        logger.error(f"Error processing Spotify request: {str(e)}")
        await Smart_Notify(bot, f"{BotCommands}sp", Exception(str(e)), status)
        if output_filename or cover_path:
            logger.info(f"Cleaning Download: {output_filename}")
            clean_download(output_filename, cover_path)

@dp.message(Command(commands=["sp", "spotify"], prefix=BotCommands))
@new_task
@SmartDefender
async def spotify_command(message: Message, bot: Bot):
    if message.reply_to_message and message.reply_to_message.text:
        input_text = message.reply_to_message.text.strip()
    else:
        command_text = message.text.strip()
        input_text = ""
        for prefix in BotCommands:
            for cmd in ["sp", "spotify"]:
                full_cmd = f"{prefix}{cmd}"
                if command_text.startswith(full_cmd):
                    input_text = command_text[len(full_cmd):].strip()
                    break
            if input_text:
                break
    if not input_text:
        await send_message(
            chat_id=message.chat.id,
            text="<b>Please provide a track Spotify URL or name</b>",
            parse_mode=ParseMode.HTML
        )
        return
    await handle_spotify_request(message, bot, input_text)