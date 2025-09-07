# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
#  Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
import os
import time
import asyncio
import subprocess
from concurrent.futures import ThreadPoolExecutor
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from pyrogram.errors import FileIdInvalid
from bot import dp, SmartPyro
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.defend import SmartDefender

DOWNLOAD_DIRECTORY = "./downloads/"
if not os.path.exists(DOWNLOAD_DIRECTORY):
    os.makedirs(DOWNLOAD_DIRECTORY)

executor = ThreadPoolExecutor(max_workers=16)

def run_ffmpeg(ffmpeg_cmd):
    subprocess.run(ffmpeg_cmd, check=True, capture_output=True)

@dp.message(Command(commands=["vnote"], prefix=BotCommands))
@new_task
@SmartDefender
async def vnote_handler(message: Message, bot: Bot):
    status_msg = None
    try:
        if not message.reply_to_message or not message.reply_to_message.video:
            status_msg = await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Reply To A Video With The Command</b>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            return
        video = message.reply_to_message.video
        if video.duration and video.duration > 60:
            status_msg = await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Video Must Be 1 Minute Or Shorter</b>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            return
        status_msg = await send_message(
            chat_id=message.chat.id,
            text="<b>Converting To Video Note...✨</b>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        user_id = message.from_user.id if message.from_user else 0
        input_path = os.path.join(DOWNLOAD_DIRECTORY, f"input_{user_id}_{int(time.time())}.mp4")
        output_path = os.path.join(DOWNLOAD_DIRECTORY, f"output_{user_id}_{int(time.time())}.mp4")
        video_file_id = video.file_id
        await SmartPyro.download_media(
            message=video_file_id,
            file_name=input_path
        )
        ffmpeg_cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", "crop='min(iw,ih):min(iw,ih)',scale=640:640",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
            "-c:a", "aac", "-b:a", "96k", "-ar", "32000",
            "-t", "60", "-movflags", "+faststart", output_path
        ]
        await asyncio.get_event_loop().run_in_executor(executor, run_ffmpeg, ffmpeg_cmd)
        await SmartPyro.send_video_note(
            chat_id=message.chat.id,
            video_note=output_path,
            length=640,
            duration=min(video.duration or 60, 60)
        )
        await delete_messages(message.chat.id, status_msg.message_id)
    except FileIdInvalid:
        await Smart_Notify(bot, "vnote", "Invalid file_id", message)
        error_text = "<b>❌ Invalid Video File</b>"
        if status_msg:
            try:
                await status_msg.edit_text(
                    text=error_text,
                    parse_mode=ParseMode.HTML
                )
            except TelegramBadRequest as edit_e:
                await Smart_Notify(bot, "vnote", edit_e, message)
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
    except Exception as e:
        await Smart_Notify(bot, "vnote", e, message)
        error_text = "<b>❌ Sorry Bro Converter API Error</b>"
        if status_msg:
            try:
                await status_msg.edit_text(
                    text=error_text,
                    parse_mode=ParseMode.HTML
                )
            except TelegramBadRequest as edit_e:
                await Smart_Notify(bot, "vnote", edit_e, message)
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
    finally:
        clean_download(input_path, output_path)