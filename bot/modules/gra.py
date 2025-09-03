import aiohttp
import asyncio
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
from config import COMMAND_PREFIX, A360APIBASEURL

async def check_grammar(text):
    url = f"{A360APIBASEURL}/eng/gmr?content={text}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                result = await response.json()
                if 'response' not in result:
                    raise ValueError("Invalid API response: 'response' key missing")
                LOGGER.info("Successfully fetched grammar correction")
                return result['response'].strip()
    except Exception as e:
        LOGGER.error(f"Grammar check API error: {str(e)}")
        return None

@dp.message(Command(commands=["gra"], prefix=BotCommands))
@new_task
async def grammar_check(message: Message, bot: Bot):
    LOGGER.info(f"Received command: '{message.text}' from user {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
    progress_message = None
    try:
        if message.reply_to_message and message.reply_to_message.text:
            user_input = message.reply_to_message.text.strip()
        else:
            args = get_args(message)
            if not args:
                progress_message = await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Provide some text or reply to a message to fix grammar</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"No text provided in chat {message.chat.id}")
                return
            user_input = ' '.join(args).strip()
        progress_message = await send_message(
            chat_id=message.chat.id,
            text="<b>Checking And Fixing Grammar Please Wait...✨</b>",
            parse_mode=ParseMode.HTML
        )
        corrected_text = await check_grammar(user_input)
        if not corrected_text:
            await delete_messages(message.chat.id, [progress_message.message_id])
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Sorry, Grammar Check API Failed</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Failed to fetch grammar correction in chat {message.chat.id}")
            return
        await delete_messages(message.chat.id, [progress_message.message_id])
        await send_message(
            chat_id=message.chat.id,
            text=f"<b>Corrected Text:</b> <code>{corrected_text}</code>",
            parse_mode=ParseMode.HTML
        )
        LOGGER.info(f"Grammar correction sent for text in chat {message.chat.id}")
    except (Exception, TelegramBadRequest) as e:
        LOGGER.error(f"Error processing grammar check in chat {message.chat.id}: {str(e)}")
        await Smart_Notify(bot, "gra", e, message)
        if progress_message:
            try:
                await delete_messages(message.chat.id, [progress_message.message_id])
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Sorry, Grammar Check API Failed</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Sent grammar check error message to chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to delete progress message in chat {message.chat.id}: {str(edit_e)}")
                await Smart_Notify(bot, "gra", edit_e, message)
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Sorry, Grammar Check API Failed</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Sent grammar check error message to chat {message.chat.id}")
        else:
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Sorry, Grammar Check API Failed</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Sent grammar check error message to chat {message.chat.id}")
