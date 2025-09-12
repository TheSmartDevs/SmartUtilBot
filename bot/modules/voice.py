# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
#  Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
import os
import time
import asyncio
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
from bot.helpers.defend import SmartDefender
from pydub import AudioSegment

DOWNLOAD_DIRECTORY = "./downloads/"
if not os.path.exists(DOWNLOAD_DIRECTORY):
    os.makedirs(DOWNLOAD_DIRECTORY)

async def convert_audio(input_path, output_path):
    audio = AudioSegment.from_file(input_path)
    audio.export(output_path, format="ogg", codec="libopus")

@dp.message(Command(commands=["voice"], prefix=BotCommands))
@new_task
@SmartDefender
async def voice_handler(message: Message, bot: Bot):
    LOGGER.info(f"Received /voice command from user: {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
    
    # Initialize all variables before try block
    progress_message = None
    input_path = None
    output_path = None
    
    try:
        if not message.reply_to_message or not (message.reply_to_message.audio or message.reply_to_message.voice or message.reply_to_message.document):
            progress_message = await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Reply To An Audio Or Voice Message</b>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            LOGGER.warning("No valid audio/voice provided for /voice command")
            return

        file_id = None
        file_extension = ""
        
        if message.reply_to_message.audio and message.reply_to_message.audio.file_name:
            file_id = message.reply_to_message.audio.file_id
            file_extension = message.reply_to_message.audio.file_name.split('.')[-1].lower()
        elif message.reply_to_message.voice:
            file_id = message.reply_to_message.voice.file_id
            file_extension = "ogg"
        elif message.reply_to_message.document and message.reply_to_message.document.file_name:
            file_id = message.reply_to_message.document.file_id
            file_extension = message.reply_to_message.document.file_name.split('.')[-1].lower()

        valid_audio_extensions = ['mp3', 'wav', 'ogg', 'm4a']
        if file_extension and file_extension not in valid_audio_extensions:
            progress_message = await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Reply To A Valid Audio File (mp3, wav, ogg, m4a)</b>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            LOGGER.warning(f"Invalid audio format provided: {file_extension}")
            return

        progress_message = await send_message(
            chat_id=message.chat.id,
            text="<b>Converting To Voice Message...✨</b>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )

        input_path = os.path.join(DOWNLOAD_DIRECTORY, f"input_{message.chat.id}.{file_extension if file_extension else 'ogg'}")
        output_path = os.path.join(DOWNLOAD_DIRECTORY, f"output_{message.chat.id}.ogg")
        
        await SmartPyro.download_media(
            message=file_id,
            file_name=input_path
        )
        LOGGER.info(f"Downloaded audio file to {input_path}")

        await convert_audio(input_path, output_path)
        LOGGER.info(f"Converted audio to voice at {output_path}")

        await SmartPyro.send_voice(
            chat_id=message.chat.id,
            voice=output_path,
            caption="",
            parse_mode=SmartParseMode.HTML
        )
        LOGGER.info("Voice message uploaded successfully")

        await delete_messages(message.chat.id, progress_message.message_id)
        LOGGER.info(f"Successfully processed /voice command for user {message.from_user.id} in chat {message.chat.id}")

    except Exception as e:
        LOGGER.error(f"Error processing /voice command in chat {message.chat.id}: {str(e)}")
        await Smart_Notify(bot, "voice", e, message)
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
                await Smart_Notify(bot, "voice", edit_e, message)
                await send_message(
                    chat_id=message.chat.id,
                    text=error_text,
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Sent error message to chat {message.chat.id}")
        else:
            await send_message(
                chat_id=message.chat.id,
                text=error_text,
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Sent error message to chat {message.chat.id}")
    finally:
        
        if input_path and os.path.exists(input_path):
            try:
                os.remove(input_path)
            except:
                pass
        if output_path and os.path.exists(output_path):
            try:
                os.remove(output_path)
            except:
                pass
