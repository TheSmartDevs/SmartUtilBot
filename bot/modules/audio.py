import os
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from pyrogram.enums import ParseMode as SmartParseMode
from bot import dp, SmartPyro
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.pgbar import progress_bar

DOWNLOAD_DIRECTORY = "./downloads/"

if not os.path.exists(DOWNLOAD_DIRECTORY):
    os.makedirs(DOWNLOAD_DIRECTORY)

executor = ThreadPoolExecutor(max_workers=5)

def convert_video_to_audio(video_file_path, audio_file_path):
    import subprocess
    process = subprocess.run(
        ["ffmpeg", "-i", video_file_path, audio_file_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    if process.returncode != 0:
        raise Exception(f"ffmpeg error: {process.stderr.decode()}")

@dp.message(Command(commands=["aud", "convert"], prefix=BotCommands))
@new_task
async def aud_handler(message: Message, bot: Bot):
    LOGGER.info(f"Received /aud or /convert command from user: {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
    progress_message = None
    try:
        if not message.reply_to_message or not message.reply_to_message.video:
            progress_message = await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Reply To A Video With The Command</b>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            LOGGER.warning("No valid video provided for /aud or /convert command")
            return

        command_parts = get_args(message)
        if not command_parts:
            progress_message = await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Provide Name For The File</b>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            LOGGER.warning("No audio file name provided for /aud or /convert command")
            return

        audio_file_name = command_parts[0]
        progress_message = await send_message(
            chat_id=message.chat.id,
            text="<b>Downloading Your File...✨</b>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )

        video_file_id = message.reply_to_message.video.file_id
        video_file_path = os.path.join(DOWNLOAD_DIRECTORY, f"video_{message.chat.id}.mp4")
        await SmartPyro.download_media(
            message=video_file_id,
            file_name=video_file_path
        )
        LOGGER.info(f"Downloaded video file to {video_file_path}")

        await progress_message.edit_text(
            text="<b>Converting To Mp3...✨</b>",
            parse_mode=ParseMode.HTML
        )

        audio_file_path = os.path.join(DOWNLOAD_DIRECTORY, f"{audio_file_name}.mp3")
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(executor, convert_video_to_audio, video_file_path, audio_file_path)
        LOGGER.info(f"Converted video to audio at {audio_file_path}")

        start_time = time.time()
        last_update_time = [start_time]
        await SmartPyro.send_audio(
            chat_id=message.chat.id,
            audio=audio_file_path,
            caption=f"<code>{audio_file_name}</code>",
            parse_mode=SmartParseMode.HTML,
            progress=progress_bar,
            progress_args=(progress_message, start_time, last_update_time)
        )
        LOGGER.info("Audio file uploaded successfully")

        await delete_messages(message.chat.id, progress_message.message_id)

    except Exception as e:
        LOGGER.error(f"Error processing /aud or /convert command in chat {message.chat.id}: {str(e)}")
        await Smart_Notify(bot, "aud/convert", e, message)
        error_text = "<b>❌ Sorry Bro Converter API Error</b>"
        if progress_message:
            try:
                await progress_message.edit_text(
                    text=error_text,
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Edited progress message with error in chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                await Smart_Notify(bot, "aud/convert", edit_e, message)
                await send_message(
                    chat_id=message.chat.id,
                    text=error_text,
                    parse_mode=ParseMode.HTML
                )
        else:
            await send_message(
                chat_id=message.chat.id,
                text=error_text,
                parse_mode=ParseMode.HTML
            )
        LOGGER.info(f"Sent error message to chat {message.chat.id}")
    finally:
        clean_download(video_file_path, audio_file_path)