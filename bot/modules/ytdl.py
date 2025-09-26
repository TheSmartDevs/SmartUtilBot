import os
import re
import io
import math
import time
import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime, timedelta
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from pyrogram.enums import ParseMode as SmartParseMode
from pyrogram.types import Message as SmartMessage
from concurrent.futures import ThreadPoolExecutor
from moviepy import VideoFileClip
from PIL import Image
import yt_dlp
from bot import dp, SmartPyro
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.pgbar import progress_bar
from bot.helpers.defend import SmartDefender
from config import YT_COOKIES_PATH, VIDEO_RESOLUTION, MAX_VIDEO_SIZE, COMMAND_PREFIX

logger = LOGGER

class Config:
    TEMP_DIR = Path("./downloads")
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    }

Config.TEMP_DIR.mkdir(exist_ok=True)

executor = ThreadPoolExecutor(max_workers=6)

def sanitize_filename(title: str) -> str:
    title = re.sub(r'[<>:"/\\|?*]', '', title[:50]).replace(' ', '_')
    return f"{title}_{int(time.time())}"

def format_size(size_bytes: int) -> str:
    if not size_bytes:
        return "0B"
    units = ("B", "KB", "MB", "GB")
    i = int(math.log(size_bytes, 1024))
    return f"{round(size_bytes / (1024 ** i), 2)} {units[i]}"

def format_duration(seconds: int) -> str:
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f"{hours}h {minutes}m {seconds}s" if hours else f"{minutes}m {seconds}s" if minutes else f"{seconds}s"

async def get_video_duration(video_path: str) -> float:
    try:
        clip = VideoFileClip(video_path)
        duration = clip.duration
        clip.close()
        return duration
    except Exception as e:
        return 0.0

def youtube_parser(url: str) -> Optional[str]:
    youtube_patterns = [
        r"(?:youtube\.com/shorts/)([^\"&?/ ]{11})(\?.*)?",
        r"(?:youtube\.com/(?:[^/]+/.+/|(?:v|e(?:mbed)?)|.*[?&]v=)|youtu\.be/)([^\"&?/ ]{11})",
        r"(?:youtube\.com/watch\?v=)([^\"&?/ ]{11})",
        r"(?:m\.youtube\.com/watch\?v=)([^\"&?/ ]{11})",
        r"(?:youtube\.com/embed/)([^\"&?/ ]{11})",
        r"(?:youtube\.com/v/)([^\"&?/ ]{11})"
    ]

    for pattern in youtube_patterns:
        match = re.search(pattern, url)
        if match:
            video_id = match.group(1)
            if "shorts" in url.lower():
                standardized_url = f"https://www.youtube.com/shorts/{video_id}"
                return standardized_url
            else:
                standardized_url = f"https://www.youtube.com/watch?v={video_id}"
                return standardized_url

    return None

def get_ydl_opts(output_path: str, is_audio: bool = False) -> dict:
    width, height = VIDEO_RESOLUTION
    base = {
        'outtmpl': output_path + '.%(ext)s',
        'cookiefile': YT_COOKIES_PATH,
        'quiet': True,
        'noprogress': True,
        'nocheckcertificate': True,
        'socket_timeout': 60,
        'retries': 3,
        'merge_output_format': 'mp4',
    }
    if is_audio:
        base.update({
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192'
            }]
        })
    else:
        base.update({
            'format': f'bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={height}]+bestaudio/best[height<={height}]/best',
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4'
            }],
            'prefer_ffmpeg': True,
            'postprocessor_args': {
                'FFmpegVideoConvertor': ['-c:v', 'libx264', '-c:a', 'aac', '-f', 'mp4']
            }
        })
    return base

async def download_media(url: str, is_audio: bool, status: Message, bot: Bot) -> Tuple[Optional[dict], Optional[str]]:
    parsed_url = youtube_parser(url)
    if not parsed_url:
        await status.edit_text("<b>Invalid YouTube ID Or URL</b>", parse_mode=ParseMode.HTML)
        await Smart_Notify(bot, f"{BotCommands}yt", Exception("Invalid YouTube URL"), status)
        return None, "Invalid YouTube URL"

    try:
        ydl_opts_info = {
            'cookiefile': YT_COOKIES_PATH,
            'quiet': True,
            'socket_timeout': 30,
            'retries': 2
        }
        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            info = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(executor, ydl.extract_info, parsed_url, False),
                timeout=45
            )

        if not info:
            await status.edit_text(f"<b>Sorry Bro {'Audio' if is_audio else 'Video'} Not Found</b>", parse_mode=ParseMode.HTML)
            await Smart_Notify(bot, f"{BotCommands}yt", Exception("No media info found"), status)
            return None, "No media info found"

        duration = info.get('duration', 0)
        if duration > 7200:
            await status.edit_text(f"<b>Sorry Bro {'Audio' if is_audio else 'Video'} Is Over 2hrs</b>", parse_mode=ParseMode.HTML)
            await Smart_Notify(bot, f"{BotCommands}yt", Exception("Media duration exceeds 2 hours"), status)
            return None, "Media duration exceeds 2 hours"

        await status.edit_text("<b>Found ☑️ Downloading...</b>", parse_mode=ParseMode.HTML)

        title = info.get('title', 'Unknown')
        safe_title = sanitize_filename(title)
        output_path = f"{Config.TEMP_DIR}/{safe_title}"

        opts = get_ydl_opts(output_path, is_audio)
        with yt_dlp.YoutubeDL(opts) as ydl:
            await asyncio.get_event_loop().run_in_executor(executor, ydl.download, [parsed_url])

        file_path = f"{output_path}.mp3" if is_audio else f"{output_path}.mp4"
        if not os.path.exists(file_path) and not is_audio:
            for ext in ['.webm', '.mkv']:
                alt_path = f"{output_path}{ext}"
                if os.path.exists(alt_path):
                    try:
                        clip = VideoFileClip(alt_path)
                        clip.write_videofile(file_path, codec='libx264', audio_codec='aac')
                        clip.close()
                        clean_download(alt_path)
                        break
                    except Exception as e:
                        clean_download(alt_path)
                        continue
                else:
                    continue

        if not os.path.exists(file_path):
            await status.edit_text(f"<b>Sorry Bro {'Audio' if is_audio else 'Video'} Not Found</b>", parse_mode=ParseMode.HTML)
            await Smart_Notify(bot, f"{BotCommands}yt", Exception(f"Download failed, file not found: {file_path}"), status)
            return None, "Download failed"

        file_size = os.path.getsize(file_path)
        if file_size > MAX_VIDEO_SIZE:
            clean_download(file_path)
            await status.edit_text(f"<b>Sorry Bro {'Audio' if is_audio else 'Video'} Is Over 2GB</b>", parse_mode=ParseMode.HTML)
            await Smart_Notify(bot, f"{BotCommands}yt", Exception("File size exceeds 2GB"), status)
            return None, "File exceeds 2GB"

        thumbnail_path = await prepare_thumbnail(info.get('thumbnail'), output_path, bot)
        duration = await get_video_duration(file_path) if not is_audio else info.get('duration', 0)

        metadata = {
            'file_path': file_path,
            'title': title,
            'views': info.get('view_count', 0),
            'duration': format_duration(int(duration)),
            'file_size': format_size(file_size),
            'thumbnail_path': thumbnail_path
        }

        return metadata, None
    except asyncio.TimeoutError:
        await status.edit_text("<b>Sorry Bro YouTubeDL API Dead</b>", parse_mode=ParseMode.HTML)
        await Smart_Notify(bot, f"{BotCommands}yt", asyncio.TimeoutError("Metadata fetch timed out"), status)
        return None, "Metadata fetch timed out"
    except Exception as e:
        await status.edit_text("<b>Sorry Bro YouTubeDL API Dead</b>", parse_mode=ParseMode.HTML)
        await Smart_Notify(bot, f"{BotCommands}yt", e, status)
        return None, f"Download failed: {str(e)}"

async def prepare_thumbnail(thumbnail_url: str, output_path: str, bot: Bot) -> Optional[str]:
    if not thumbnail_url:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail_url) as resp:
                if resp.status != 200:
                    await Smart_Notify(bot, f"{BotCommands}yt", Exception(f"Failed to fetch thumbnail, status: {resp.status}"), None)
                    return None
                data = await resp.read()

        thumbnail_path = f"{output_path}_thumb.jpg"
        with Image.open(io.BytesIO(data)) as img:
            img.convert('RGB').save(thumbnail_path, "JPEG", quality=85)
        return thumbnail_path
    except Exception as e:
        await Smart_Notify(bot, f"{BotCommands}yt", e, None)
        return None

async def search_youtube(query: str, retries: int = 2, bot: Bot = None) -> Optional[str]:
    opts = {
        'default_search': 'ytsearch1',
        'cookiefile': YT_COOKIES_PATH,
        'quiet': True,
        'simulate': True,
    }

    for attempt in range(retries):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = await asyncio.get_event_loop().run_in_executor(executor, ydl.extract_info, query, False)
                if info.get('entries'):
                    url = info['entries'][0]['webpage_url']
                    return url

                simplified_query = re.sub(r'[^\w\s]', '', query).strip()
                if simplified_query != query:
                    info = await asyncio.get_event_loop().run_in_executor(executor, ydl.extract_info, simplified_query, False)
                    if info.get('entries'):
                        url = info['entries'][0]['webpage_url']
                        return url
        except Exception as e:
            if attempt == retries - 1:
                await Smart_Notify(bot, f"{BotCommands}yt", e, None)
            if attempt < retries - 1:
                await asyncio.sleep(1)
    return None

async def handle_media_request(message: Message, bot: Bot, query: str, is_audio: bool = False):
    status = await send_message(
        chat_id=message.chat.id,
        text=f"<b>Searching The {'Audio' if is_audio else 'Video'}</b>",
        parse_mode=ParseMode.HTML
    )

    user_name = f"{message.from_user.first_name}{' ' + message.from_user.last_name if message.from_user.last_name else ''}" if message.from_user else message.chat.title
    user_id = message.from_user.id if message.from_user else message.chat.id
    media_type = "Audio" if is_audio else "Video"

    logger.info(f"{user_name} {user_id} Query - {query} Type - {media_type}")

    video_url = youtube_parser(query)
    if not video_url:
        logger.info(f"{user_name} {user_id} Processing query - {query}")
        video_url = await search_youtube(query, bot=bot)
        if video_url:
            logger.info(f"{user_name} {user_id} Selected URL - {video_url} Type - {media_type}")
        else:
            logger.info(f"{user_name} {user_id} No results found for query - {query} Type - {media_type}")
            await status.edit_text(f"<b>Sorry Bro {'Audio' if is_audio else 'Video'} Not Found</b>", parse_mode=ParseMode.HTML)
            await Smart_Notify(bot, f"{BotCommands}yt", Exception("No video URL found"), message)
            return
    else:
        logger.info(f"{user_name} {user_id} URL - {video_url} Type - {media_type}")

    result, error = await download_media(video_url, is_audio, status, bot)
    if error:
        return

    user_info = (
        f"<a href=\"tg://user?id={message.from_user.id}\">{user_name}</a>" if message.from_user
        else f"<a href=\"https://t.me/{message.chat.username or 'this group'}\">{message.chat.title}</a>"
    )
    caption = (
        f"🎵 <b>Title:</b> <code>{result['title']}</code>\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"👁️‍🗨️ <b>Views:</b> {result['views']}\n"
        f"<b>🔗 Url:</b> <a href=\"{video_url}\">Watch On YouTube</a>\n"
        f"⏱️ <b>Duration:</b> {result['duration']}\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"<b>Downloaded By</b> {user_info}"
    )

    last_update_time = [0]
    start_time = time.time()
    send_func = SmartPyro.send_audio if is_audio else SmartPyro.send_video
    kwargs = {
        'chat_id': message.chat.id,
        'caption': caption,
        'parse_mode': SmartParseMode.HTML,
        'thumb': result['thumbnail_path'],
        'progress': progress_bar,
        'progress_args': (status, start_time, last_update_time)
    }
    if is_audio:
        kwargs.update({'audio': result['file_path'], 'title': result['title']})
    else:
        kwargs.update({
            'video': result['file_path'],
            'supports_streaming': True,
            'height': 720,
            'width': 1280,
            'duration': int(await get_video_duration(result['file_path']))
        })

    try:
        await send_func(**kwargs)
        await delete_messages(message.chat.id, [status.message_id])
    except Exception as e:
        await status.edit_text("<b>Sorry Bro YouTubeDL API Dead</b>", parse_mode=ParseMode.HTML)
        await Smart_Notify(bot, f"{BotCommands}yt", e, message)
        return

    clean_download(result['file_path'], result['thumbnail_path'])

@dp.message(Command(commands=["yt", "video"], prefix=BotCommands))
@new_task
@SmartDefender
async def video_command(message: Message, bot: Bot):
    if message.reply_to_message and message.reply_to_message.text:
        query = message.reply_to_message.text.strip()
    else:
        command_text = message.text.strip()
        query = ""
        for prefix in COMMAND_PREFIX:
            for cmd in ["yt", "video"]:
                full_cmd = f"{prefix}{cmd}"
                if command_text.startswith(full_cmd):
                    query = command_text[len(full_cmd):].strip()
                    break
            if query:
                break

    if not query:
        await send_message(
            chat_id=message.chat.id,
            text="<b>Please provide a video name or link ❌</b>",
            parse_mode=ParseMode.HTML
        )
        return

    await handle_media_request(message, bot, query)

@dp.message(Command(commands=["song", "mp3"], prefix=BotCommands))
@new_task
@SmartDefender
async def song_command(message: Message, bot: Bot):
    if message.reply_to_message and message.reply_to_message.text:
        query = message.reply_to_message.text.strip()
    else:
        command_text = message.text.strip()
        query = ""
        for prefix in COMMAND_PREFIX:
            for cmd in ["song", "mp3"]:
                full_cmd = f"{prefix}{cmd}"
                if command_text.startswith(full_cmd):
                    query = command_text[len(full_cmd):].strip()
                    break
            if query:
                break

    if not query:
        await send_message(
            chat_id=message.chat.id,
            text="<b>Please provide a music name or link ❌</b>",
            parse_mode=ParseMode.HTML
        )
        return

    await handle_media_request(message, bot, query, is_audio=True)