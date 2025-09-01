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
from config import GROQ_API_KEY, GROQ_API_URL, TEXT_MODEL
import aiohttp
import asyncio
import re

def sanitize_html(text):
    text = re.sub(r'</?think[^>]*>', '', text, flags=re.IGNORECASE)
    return text

@dp.message(Command(commands=["dep"], prefix=BotCommands))
@new_task
async def dep_handler(message: Message, bot: Bot):
    LOGGER.info(f"Received command: '{message.text}' from user {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
    progress_message = None
    try:
        progress_message = await send_message(
            chat_id=message.chat.id,
            text="<b>DeepSeek AI Is Thinking Wait.. ✨</b>",
            parse_mode=ParseMode.HTML
        )

        user_text = None
        command_text = message.text.split(maxsplit=1)
        if message.reply_to_message and message.reply_to_message.text:
            user_text = message.reply_to_message.text
        elif len(command_text) > 1:
            user_text = command_text[1]

        if not user_text:
            await progress_message.edit_text(
                text="<b>Please Provide A Prompt For DeepSeekAI ✨ Response</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Prompt missing for DeepSeekAI command in chat {message.chat.id}")
            return

        async with aiohttp.ClientSession() as session:
            async with session.post(
                GROQ_API_URL,
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": TEXT_MODEL,
                    "messages": [
                        {"role": "system", "content": "Reply in the same language as the user's message But Always Try To Answer Shortly"},
                        {"role": "user", "content": user_text},
                    ],
                }
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    bot_response = data.get("choices", [{}])[0].get("message", {}).get("content", "Sorry DeepSeek API Dead")
                    bot_response = sanitize_html(bot_response)
                else:
                    error_response = await response.text()
                    LOGGER.error(f"DeepSeekAI API request failed with status {response.status}: {error_response}")
                    bot_response = "<b>❌ Sorry Bro DeepSeekAI ✨ API Dead</b>"

        if len(bot_response) > 4000:
            await delete_messages(message.chat.id, progress_message.message_id)
            parts = [bot_response[i:i+4000] for i in range(0, len(bot_response), 4000)]
            for part in parts:
                await send_message(
                    chat_id=message.chat.id,
                    text=part,
                    parse_mode=ParseMode.HTML
                )
            LOGGER.info(f"Successfully sent DeepSeekAI response (split) to chat {message.chat.id}")
        else:
            try:
                await progress_message.edit_text(
                    text=bot_response,
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Successfully sent DeepSeekAI response to chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                await delete_messages(message.chat.id, progress_message.message_id)
                await send_message(
                    chat_id=message.chat.id,
                    text=bot_response,
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Successfully sent DeepSeekAI response to chat {message.chat.id}")
    except Exception as e:
        LOGGER.error(f"DeepSeekAI error in chat {message.chat.id}: {str(e)}")
        if progress_message:
            try:
                await progress_message.edit_text(
                    text="<b>❌ Sorry Bro DeepSeekAI ✨ API Dead</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Edited progress message with DeepSeekAI error in chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Sorry Bro DeepSeekAI ✨ API Dead</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Sent DeepSeekAI error message to chat {message.chat.id}")
        else:
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Sorry Bro DeepSeekAI ✨ API Dead</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Sent DeepSeekAI error message to chat {message.chat.id}")