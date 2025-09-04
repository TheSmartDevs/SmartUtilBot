import os
import aiohttp
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from bot import dp
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from config import A360APIBASEURL

DOWNLOAD_DIRECTORY = "./downloads/"

if not os.path.exists(DOWNLOAD_DIRECTORY):
    os.makedirs(DOWNLOAD_DIRECTORY)

async def fetch_pronunciation_info(word):
    url = f"{A360APIBASEURL}/eng/prn?word={word}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                result = await response.json()
                pronunciation_info = result['response']
                LOGGER.info(f"Successfully fetched pronunciation info for '{word}'")
                return {
                    "word": pronunciation_info['Word'],
                    "breakdown": pronunciation_info['- Breakdown'],
                    "pronunciation": pronunciation_info['- Pronunciation'],
                    "stems": pronunciation_info['Word Stems'].split(", "),
                    "definition": pronunciation_info['Definition'],
                    "audio_link": pronunciation_info['Audio']
                }
    except (aiohttp.ClientError, ValueError, KeyError) as e:
        LOGGER.error(f"Pronunciation API error for word '{word}': {e}")
        return None

@dp.message(Command(commands=["prn"], prefix=BotCommands))
@new_task
async def prn_handler(message: Message, bot: Bot):
    LOGGER.info(f"Received /prn command from user: {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
    checking_message = None
    try:
        if message.reply_to_message and message.reply_to_message.text:
            word = message.reply_to_message.text.strip()
            if len(word.split()) != 1:
                checking_message = await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Reply To A Message With A Single Word</b>",
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
                LOGGER.warning(f"Invalid reply format: {word}")
                return
        else:
            command_parts = get_args(message)
            if not command_parts or len(command_parts) != 1:
                checking_message = await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Provide A Single Word To Check Pronunciation</b>",
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
                LOGGER.warning(f"Invalid command format: {message.text}")
                return
            word = command_parts[0].strip()

        checking_message = await send_message(
            chat_id=message.chat.id,
            text="<b>Checking Pronunciation...✨</b>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )

        pronunciation_info = await fetch_pronunciation_info(word)
        if pronunciation_info is None:
            error_text = "<b>❌ Sorry Bro Pronunciation API Dead</b>"
            try:
                await checking_message.edit_text(
                    text=error_text,
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Edited checking message with error in chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit checking message in chat {message.chat.id}: {str(edit_e)}")
                await Smart_Notify(bot, "prn", edit_e, message)
                await send_message(
                    chat_id=message.chat.id,
                    text=error_text,
                    parse_mode=ParseMode.HTML
                )
            LOGGER.error(f"Pronunciation API returned no data for word '{word}'")
            await Smart_Notify(bot, "prn", Exception("Pronunciation API returned no data"), message)
            return

        audio_filename = None
        if pronunciation_info['audio_link']:
            audio_filename = os.path.join(DOWNLOAD_DIRECTORY, f"prn_{message.chat.id}_{word}.mp3")
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(pronunciation_info['audio_link']) as response:
                        response.raise_for_status()
                        with open(audio_filename, 'wb') as f:
                            f.write(await response.read())
                LOGGER.info(f"Downloaded audio for word '{word}' to {audio_filename}")
            except aiohttp.ClientError as e:
                LOGGER.error(f"Failed to download audio for word '{word}': {e}")
                await Smart_Notify(bot, "prn audio", e, message)
                audio_filename = None

        caption = (
            f"<b>Word:</b> {pronunciation_info['word']}\n"
            f"<b>- Breakdown:</b> {pronunciation_info['breakdown']}\n"
            f"<b>- Pronunciation:</b> {pronunciation_info['pronunciation']}\n\n"
            f"<b>Word Stems:</b>\n{', '.join(pronunciation_info['stems'])}\n\n"
            f"<b>Definition:</b>\n{pronunciation_info['definition']}"
        )

        if audio_filename:
            await bot.send_audio(
                chat_id=message.chat.id,
                audio=FSInputFile(audio_filename),
                caption=caption,
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Sent audio pronunciation for '{word}'")
        else:
            await send_message(
                chat_id=message.chat.id,
                text=caption,
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Sent text pronunciation for '{word}'")

        await delete_messages(message.chat.id, checking_message.message_id)

    except Exception as e:
        LOGGER.error(f"Error processing /prn command for word '{word}': {str(e)}")
        await Smart_Notify(bot, "prn", e, message)
        error_text = "<b>❌ Sorry Bro Pronunciation API Dead</b>"
        if checking_message:
            try:
                await checking_message.edit_text(
                    text=error_text,
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Edited checking message with error in chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit checking message in chat {message.chat.id}: {str(edit_e)}")
                await Smart_Notify(bot, "prn", edit_e, message)
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
        if audio_filename and os.path.exists(audio_filename):
            clean_download(audio_filename)