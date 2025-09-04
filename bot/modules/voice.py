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
from bot.helpers.pgbar import progress_bar
from pydub import AudioSegment

DOWNLOAD_DIRECTORY = "./downloads/"

if not os.path.exists(DOWNLOAD_DIRECTORY):
    os.makedirs(DOWNLOAD_DIRECTORY)

async def convert_audio(input_path, output_path):
    audio = AudioSegment.from_file(input_path)
    audio.export(output_path, format="ogg", codec="libopus")

@dp.message(Command(commands=["voice"], prefix=BotCommands))
@new_task
async def voice_handler(message: Message, bot: Bot):
    LOGGER.info(f"Received /voice command from user: {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
    progress_message = None
    try:
        if not message.reply_to_message or not (message.reply_to_message.audio or message.reply_to_message.voice or message.reply_to_message.document):
            progress_message = await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Reply To An Audio Or Voice Message</b>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            LOGGER.warning("No valid audio or voice message provided for /voice command")
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
            LOGGER.warning(f"Invalid audio file extension: {file_extension}")
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
        LOGGER.info(f"Converted audio to {output_path}")

        start_time = time.time()
        last_update_time = [start_time]
        await SmartPyro.send_voice(
            chat_id=message.chat.id,
            voice=output_path,
            caption="",
            parse_mode=SmartParseMode.HTML,
            progress=progress_bar,
            progress_args=(progress_message, start_time, last_update_time)
        )
        LOGGER.info("Voice message uploaded successfully")

        await delete_messages(message.chat.id, progress_message.message_id)

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
        else:
            await send_message(
                chat_id=message.chat.id,
                text=error_text,
                parse_mode=ParseMode.HTML
            )
        LOGGER.info(f"Sent error message to chat {message.chat.id}")
    finally:
        clean_download(input_path, output_path)