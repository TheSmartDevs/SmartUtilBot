# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
#  Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
import aiohttp
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from bot import dp
from bot.helpers.utils import new_task
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.defend import SmartDefender
from config import A360APIBASEURL

async def fetch_synonyms_antonyms(word):
    synonyms_url = f"{A360APIBASEURL}/eng/syn?word={word}"
    antonyms_url = f"{A360APIBASEURL}/eng/ant?word={word}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(synonyms_url) as syn_response, session.get(antonyms_url) as ant_response:
                syn_response.raise_for_status()
                ant_response.raise_for_status()
                synonyms = await syn_response.json()
                antonyms = await ant_response.json()
                synonyms = synonyms['response']
                antonyms = antonyms['response']
        LOGGER.info(f"Successfully fetched synonyms and antonyms for '{word}'")
        return synonyms, antonyms
    except (aiohttp.ClientError, ValueError, KeyError) as e:
        LOGGER.error(f"A360 API error for word '{word}': {e}")
        raise

@dp.message(Command(commands=["syn", "synonym"], prefix=BotCommands))
@new_task
@SmartDefender
async def syn_handler(message: Message, bot: Bot):
    LOGGER.info(f"Received /syn or /synonym command from user: {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
    loading_message = None
    try:
        if message.reply_to_message and message.reply_to_message.text:
            word = message.reply_to_message.text.strip()
            if len(word.split()) != 1:
                loading_message = await send_message(
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
                loading_message = await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Provide A Single Word To Get Synonyms And Antonyms</b>",
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
                LOGGER.warning(f"Invalid command format: {message.text}")
                return
            word = command_parts[0].strip()
        loading_message = await send_message(
            chat_id=message.chat.id,
            text="<b>Fetching Synonyms and Antonyms...✨</b>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        synonyms, antonyms = await fetch_synonyms_antonyms(word)
        synonyms_text = ", ".join(synonyms) if synonyms else "No synonyms found"
        antonyms_text = ", ".join(antonyms) if antonyms else "No antonyms found"
        response_text = (
            f"<b>Synonyms:</b>\n{synonyms_text}\n\n"
            f"<b>Antonyms:</b>\n{antonyms_text}"
        )
        await loading_message.edit_text(
            text=response_text,
            parse_mode=ParseMode.HTML
        )
        LOGGER.info(f"Sent synonyms and antonyms for '{word}' in chat {message.chat.id}")
    except Exception as e:
        LOGGER.error(f"Error processing /syn or /synonym command for word '{word}': {str(e)}")
        await Smart_Notify(bot, "syn", e, message)
        error_text = "<b>❌ Sorry Bro Synonym/Antonym API Failed</b>"
        if loading_message:
            try:
                await loading_message.edit_text(
                    text=error_text,
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Edited loading message with error in chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit loading message in chat {message.chat.id}: {str(edit_e)}")
                await Smart_Notify(bot, "syn", edit_e, message)
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