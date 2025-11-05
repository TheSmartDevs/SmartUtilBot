import os
import re
import io
import math
import time
import asyncio
import aiohttp
from pathlib import Path
from typing import Optional, Tuple, Dict
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
import yt_dlp
from py_yt import VideosSearch, Search
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.enums import ParseMode
from pyrogram.enums import ParseMode as SmartParseMode
from pyrogram.types import InputMediaDocument
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

class DLConfig:
    TEMP_DIR = Path("./downloads")
    YT_COOKIES_PATH = YT_COOKIES_PATH
    VIDEO_RESOLUTION = VIDEO_RESOLUTION
    MAX_VIDEO_SIZE = MAX_VIDEO_SIZE
    COMMAND_PREFIX = COMMAND_PREFIX
    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0.4472.124',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
    }
    SOCKET_TIMEOUT = 60
    RETRIES = 3
    MAX_DURATION = 7200
    THUMBNAIL_QUALITY = 85
    AUDIO_QUALITY = '320'
    METADATA_TIMEOUT = 45
    SEARCH_RETRIES = 2
    EXECUTOR_WORKERS = 8

DLConfig.TEMP_DIR.mkdir(exist_ok=True)

executor = ThreadPoolExecutor(max_workers=DLConfig.EXECUTOR_WORKERS)

def sanitize_filename(title: str) -> str:
    title = re.sub(r'[<>:"/\\|?*]', '', title[:100])
    title = re.sub(r'\s+', '_', title.strip())
    return title

def generate_temp_id() -> str:
    return str(int(time.time() * 1000) % 100000)

def format_size(size_bytes: int) -> str:
    if not size_bytes:
        return "0B"
    units = ("B", "KB", "MB", "GB")
    i = int(math.log(size_bytes, 1024)) if size_bytes > 0 else 0
    return f"{round(size_bytes / (1024 ** i), 2)} {units[i]}"

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
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f"{hours}h {minutes}m {seconds}s" if hours else f"{minutes}m {seconds}s" if minutes else f"{seconds}s"

def parse_view_count(view_text: str) -> int:
    try:
        view_text = view_text.replace(',', '').replace(' views', '').replace(' view', '')
        if 'M' in view_text:
            return int(float(view_text.replace('M', '')) * 1000000)
        elif 'K' in view_text:
            return int(float(view_text.replace('K', '')) * 1000)
        else:
            return int(view_text)
    except:
        return 0

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

def extract_video_id(url: str) -> Optional[str]:
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
        r"youtu\.be\/([0-9A-Za-z_-]{11})"
    ]
    for pat in patterns:
        match = re.search(pat, url)
        if match:
            return match.group(1)
    return url if len(url) == 11 else None

def get_ydl_opts(output_path: str, is_audio: bool = False) -> dict:
    width, height = DLConfig.VIDEO_RESOLUTION
    base = {
        'outtmpl': output_path + '.%(ext)s',
        'cookiefile': DLConfig.YT_COOKIES_PATH,
        'quiet': True,
        'no_warnings': True,
        'noprogress': True,
        'nocheckcertificate': True,
        'socket_timeout': DLConfig.SOCKET_TIMEOUT,
        'retries': DLConfig.RETRIES,
        'concurrent_fragment_downloads': 5,
    }
    if is_audio:
        base.update({
            'format': 'bestaudio/best',
            'extractaudio': True,
            'audioformat': 'mp3',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': DLConfig.AUDIO_QUALITY,
            }],
        })
    else:
        base.update({
            'format': f'bestvideo[height<={height}][ext=mp4]+bestaudio[ext=m4a]/bestvideo[height<={height}]+bestaudio/best[height<={height}]/best',
            'merge_output_format': 'mp4',
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4'
            }],
            'prefer_ffmpeg': True,
            'postprocessor_args': {
                'FFmpegVideoConvertor': ['-c:v', 'libx264', '-preset', 'ultrafast', '-c:a', 'aac', '-f', 'mp4']
            }
        })
    return base

async def fetch_video_metadata(video_id: str) -> Optional[dict]:
    try:
        src = VideosSearch(video_id, limit=1, language="en", region="US")
        data = await src.next()
        if data and data.get('result') and len(data['result']) > 0:
            return data['result'][0]
        return None
    except Exception as e:
        return None

async def download_thumbnail(thumbnail_url: str, output_path: str) -> Optional[str]:
    if not thumbnail_url:
        return None
    try:
        connector = aiohttp.TCPConnector(limit=10, ttl_dns_cache=300)
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout, headers=DLConfig.HEADERS) as session:
            async with session.get(thumbnail_url) as resp:
                if resp.status != 200:
                    return None
                data = await resp.read()

        thumbnail_path = f"{output_path}_thumb.jpg"
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            executor,
            lambda: Image.open(io.BytesIO(data)).convert('RGB').save(thumbnail_path, "JPEG", quality=DLConfig.THUMBNAIL_QUALITY, optimize=True)
        )
        return thumbnail_path
    except Exception as e:
        return None

async def download_media_file(url: str, is_audio: bool, temp_id: str) -> Optional[str]:
    temp_dir = DLConfig.TEMP_DIR / temp_id
    temp_dir.mkdir(exist_ok=True)
    
    output_path = str(temp_dir / "media")
    opts = get_ydl_opts(output_path, is_audio)
    
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            await asyncio.get_event_loop().run_in_executor(executor, ydl.download, [url])
        
        expected_ext = 'mp3' if is_audio else 'mp4'
        file_path = f"{output_path}.{expected_ext}"
        
        if not os.path.exists(file_path):
            for ext in ['.mp3', '.m4a', '.webm', '.mkv', '.mp4']:
                alt_path = f"{output_path}{ext}"
                if os.path.exists(alt_path):
                    if ext == expected_ext or (is_audio and ext in ['.mp3', '.m4a']):
                        file_path = alt_path
                        break
                    else:
                        file_path = alt_path
                        break
        
        return file_path if os.path.exists(file_path) else None
    except Exception as e:
        return None

async def download_media(url: str, is_audio: bool, status: Message, bot: Bot) -> Tuple[Optional[dict], Optional[str]]:
    parsed_url = youtube_parser(url)
    if not parsed_url:
        await status.edit_text("<b>Invalid YouTube ID Or URL</b>", parse_mode=ParseMode.HTML)
        await Smart_Notify(bot, f"{BotCommands}yt", Exception("Invalid YouTube URL"), status)
        return None, "Invalid YouTube URL"

    try:
        temp_id = generate_temp_id()
        video_id = extract_video_id(parsed_url)
        
        if not video_id:
            await status.edit_text("<b>Invalid YouTube ID Or URL</b>", parse_mode=ParseMode.HTML)
            await Smart_Notify(bot, f"{BotCommands}yt", Exception("Invalid YouTube URL"), status)
            return None, "Invalid YouTube URL"
        
        info = await fetch_video_metadata(video_id)
        
        if not info:
            await status.edit_text(f"<b>Sorry Bro {'Audio' if is_audio else 'Video'} Not Found</b>", parse_mode=ParseMode.HTML)
            await Smart_Notify(bot, f"{BotCommands}yt", Exception("No media info found"), status)
            return None, "No media info found"

        duration_str = info.get('duration', '0:00')
        duration = parse_duration_to_seconds(duration_str)
        
        if duration > DLConfig.MAX_DURATION:
            await status.edit_text(f"<b>Sorry Bro {'Audio' if is_audio else 'Video'} Is Over 2hrs</b>", parse_mode=ParseMode.HTML)
            await Smart_Notify(bot, f"{BotCommands}yt", Exception("Media duration exceeds 2 hours"), status)
            return None, "Media duration exceeds 2 hours"

        await status.edit_text("<b>Found ☑️ Downloading...</b>", parse_mode=ParseMode.HTML)

        title = info.get('title', 'Unknown')
        safe_title = sanitize_filename(title)
        
        thumbnails = info.get('thumbnails', [])
        thumbnail_url = thumbnails[-1]['url'] if thumbnails else None
        
        view_count_data = info.get('viewCount', {})
        view_count = parse_view_count(view_count_data.get('short', '0'))
        
        thumbnail_task = asyncio.create_task(download_thumbnail(thumbnail_url, str(DLConfig.TEMP_DIR / temp_id / "thumb")))
        download_task = asyncio.create_task(download_media_file(parsed_url, is_audio, temp_id))
        
        results = await asyncio.gather(thumbnail_task, download_task, return_exceptions=True)
        thumbnail_path = results[0] if not isinstance(results[0], Exception) else None
        file_path = results[1] if not isinstance(results[1], Exception) else None

        if not file_path or not os.path.exists(file_path):
            await status.edit_text(f"<b>Sorry Bro {'Audio' if is_audio else 'Video'} Not Found</b>", parse_mode=ParseMode.HTML)
            await Smart_Notify(bot, f"{BotCommands}yt", Exception(f"Download failed, file not found: {file_path}"), status)
            logger.info(f"Cleaning Download: {DLConfig.TEMP_DIR / temp_id}/")
            return None, "Download failed"

        file_size = os.path.getsize(file_path)
        if file_size > DLConfig.MAX_VIDEO_SIZE:
            logger.info(f"Removing {'MP3' if is_audio else 'video'} file at path: {file_path}")
            await asyncio.get_event_loop().run_in_executor(executor, clean_download, file_path)
            logger.info(f"Successfully removed {'MP3' if is_audio else 'video'} file: {file_path}")
            logger.info(f"Cleaning Download: {DLConfig.TEMP_DIR / temp_id}/")
            await status.edit_text(f"<b>Sorry Bro {'Audio' if is_audio else 'Video'} Is Over 2GB</b>", parse_mode=ParseMode.HTML)
            await Smart_Notify(bot, f"{BotCommands}yt", Exception("File size exceeds 2GB"), status)
            return None, "File exceeds 2GB"

        metadata = {
            'file_path': file_path,
            'title': title,
            'safe_title': safe_title,
            'views': view_count,
            'duration': format_duration(duration),
            'duration_seconds': duration,
            'file_size': format_size(file_size),
            'thumbnail_path': thumbnail_path,
            'temp_id': temp_id
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

async def search_youtube(query: str, retries: int = 2, bot: Bot = None) -> Optional[str]:
    for attempt in range(retries):
        try:
            src = Search(query, limit=1, language="en", region="US")
            data = await src.next()
            
            if data and data.get('result') and len(data['result']) > 0:
                result = data['result'][0]
                if result.get('type') == 'video':
                    return result.get('link')
            
            simplified_query = re.sub(r'[^\w\s]', '', query).strip()
            if simplified_query != query:
                src = Search(simplified_query, limit=1, language="en", region="US")
                data = await src.next()
                if data and data.get('result') and len(data['result']) > 0:
                    result = data['result'][0]
                    if result.get('type') == 'video':
                        return result.get('link')
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
    
    file_ext = 'mp3' if is_audio else 'mp4'
    final_filename = f"{result['safe_title']}.{file_ext}"
    
    kwargs = {
        'chat_id': message.chat.id,
        'caption': caption,
        'parse_mode': SmartParseMode.HTML,
        'thumb': result['thumbnail_path'],
        'progress': progress_bar,
        'progress_args': (status, start_time, last_update_time),
        'file_name': final_filename
    }
    if is_audio:
        kwargs.update({'audio': result['file_path'], 'title': result['title']})
    else:
        kwargs.update({
            'video': result['file_path'],
            'supports_streaming': True,
            'height': 720,
            'width': 1280,
            'duration': result['duration_seconds']
        })

    try:
        await send_func(**kwargs)
        await delete_messages(message.chat.id, [status.message_id])
    except Exception as e:
        await status.edit_text("<b>Sorry Bro YouTubeDL API Dead</b>", parse_mode=ParseMode.HTML)
        await Smart_Notify(bot, f"{BotCommands}yt", e, message)
        logger.info(f"Cleaning Download: {DLConfig.TEMP_DIR / result['temp_id']}/")
        await asyncio.get_event_loop().run_in_executor(executor, clean_download, str(DLConfig.TEMP_DIR / result['temp_id']))
        return

    logger.info(f"Removing {'MP3' if is_audio else 'video'} file at path: {result['file_path']}")
    if result['thumbnail_path']:
        logger.info(f"Cleaning Download: {result['thumbnail_path']}")
    logger.info(f"Cleaning Download: {DLConfig.TEMP_DIR / result['temp_id']}/")
    await asyncio.get_event_loop().run_in_executor(executor, clean_download, str(DLConfig.TEMP_DIR / result['temp_id']))
    logger.info(f"Successfully removed {'MP3' if is_audio else 'video'} file: {result['file_path']}")

@dp.message(Command(commands=["yt", "video", " mp4"], prefix=BotCommands))
@new_task
@SmartDefender
async def video_command(message: Message, bot: Bot):
    if message.reply_to_message and message.reply_to_message.text:
        query = message.reply_to_message.text.strip()
    else:
        command_text = message.text.strip()
        query = ""
        for prefix in DLConfig.COMMAND_PREFIX:
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
        for prefix in DLConfig.COMMAND_PREFIX:
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