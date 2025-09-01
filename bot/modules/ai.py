from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from bot import dp
from bot.helpers.botutils import send_message, delete_messages
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.utils import new_task
import aiohttp

@dp.message(Command(commands=["ai"], prefix=BotCommands))
@new_task
async def ai_handler(message: Message, bot: Bot):
    LOGGER.info(f"Received command: '{message.text}' from user {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
    progress_message = None
    try:
        progress_message = await send_message(
            chat_id=message.chat.id,
            text="<b>🔍 SmartAI is thinking, Please Wait ✨</b>",
            parse_mode=ParseMode.HTML
        )

        prompt = None
        command_text = message.text.split(maxsplit=1)
        if message.reply_to_message and message.reply_to_message.text:
            prompt = message.reply_to_message.text
        elif len(command_text) > 1:
            prompt = command_text[1]

        if not prompt:
            await progress_message.edit_text(
                text="<b>Please Provide A Prompt For SmartAI ✨ Response</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Prompt missing for SmartAI command in chat {message.chat.id}")
            return

        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://abirthetech.serv00.net/ai.php?prompt={prompt}") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    response_text = data.get("response", "No response received")
                else:
                    response_text = "<b>❌ Sorry Bro SmartAI API Error</b>"
                    LOGGER.error(f"SmartAI API request failed with status {resp.status}: {await resp.text()}")

        if len(response_text) > 4000:
            await delete_messages(message.chat.id, progress_message.message_id)
            parts = [response_text[i:i+4000] for i in range(0, len(response_text), 4000)]
            for part in parts:
                await send_message(
                    chat_id=message.chat.id,
                    text=part,
                    parse_mode=ParseMode.HTML
                )
            LOGGER.info(f"Successfully sent SmartAI response (split) to chat {message.chat.id}")
        else:
            try:
                await progress_message.edit_text(
                    text=response_text,
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Successfully sent SmartAI response to chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                await delete_messages(message.chat.id, progress_message.message_id)
                await send_message(
                    chat_id=message.chat.id,
                    text=response_text,
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Successfully sent SmartAI response to chat {message.chat.id}")
    except Exception as e:
        LOGGER.error(f"SmartAI error in chat {message.chat.id}: {str(e)}")
        if progress_message:
            try:
                await progress_message.edit_text(
                    text="<b>❌ Sorry Bro SmartAI API Error</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Edited progress message with SmartAI error in chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Sorry Bro SmartAI API Error</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Sent SmartAI error message to chat {message.chat.id}")
        else:
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Sorry Bro SmartAI API Error</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Sent SmartAI error message to chat {message.chat.id}")