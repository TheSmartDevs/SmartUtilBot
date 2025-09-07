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

async def check_spelling(word):
    url = f"{A360APIBASEURL}/eng/spl?word={word}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                result = await response.json()
                if 'response' not in result:
                    raise ValueError("Invalid API response: 'response' key missing")
                LOGGER.info(f"Successfully fetched spelling correction for '{word}'")
                return result['response'].strip()
    except Exception as e:
        LOGGER.error(f"Spelling check API error for word '{word}': {e}")
        raise

@dp.message(Command(commands=["spell"], prefix=BotCommands))
@new_task
@SmartDefender
async def spell_handler(message: Message, bot: Bot):
    LOGGER.info(f"Received /spell command from user: {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
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
                    text="<b>❌ Provide A Single Word To Check Spelling</b>",
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
                LOGGER.warning(f"Invalid command format: {message.text}")
                return
            word = command_parts[0].strip()
        checking_message = await send_message(
            chat_id=message.chat.id,
            text="<b>Checking Spelling...✨</b>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        corrected_word = await check_spelling(word)
        await checking_message.edit_text(
            text=f"<code>{corrected_word}</code>",
            parse_mode=ParseMode.HTML
        )
        LOGGER.info(f"Spelling correction sent for '{word}' in chat {message.chat.id}")
    except Exception as e:
        LOGGER.error(f"Error processing /spell command for word '{word}': {str(e)}")
        await Smart_Notify(bot, "spell", e, message)
        error_text = "<b>❌ Sorry Bro Spelling Check API Failed</b>"
        if checking_message:
            try:
                await checking_message.edit_text(
                    text=error_text,
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Edited checking message with error in chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit checking message in chat {message.chat.id}: {str(edit_e)}")
                await Smart_Notify(bot, "spell", edit_e, message)
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