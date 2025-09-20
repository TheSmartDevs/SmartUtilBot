# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
#  Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
import aiohttp
import asyncio
import re
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
from bot.helpers.notify import Smart_Notify
from bot.helpers.defend import SmartDefender
from config import GROQ_API_KEY, GROQ_API_URL, TEXT_MODEL

def escape_html(text):
    html_escape_table = {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        "`": "&#96;",
        "\"": "&quot;",
        "'": "&apos;"
    }
    return "".join(html_escape_table.get(c, c) for c in text)

def format_code_response(text):
    text = re.sub(r'</?think[^>]*>', '', text, flags=re.IGNORECASE)
    replacements = [
        (r"^> (.*)", r"<blockquote>\1</blockquote>"),
        (r"```(?:\w*)\n([\s\S]*?)\n```", r"<pre>\1</pre>"),
        (r"`(.*?)`", r"<code>\1</code>"),
        (r"\*\*(.*?)\*\*", r"<b>\1</b>"),
        (r"\*(.*?)\*", r"<i>\1</i>"),
        (r"__(.*?)__", r"<i>\1</i>"),
        (r"_(.*?)_", r"<i>\1</i>"),
        (r"~~(.*?)~~", r"<s>\1</s>"),
        (r"\[(.*?)\]\((.*?)\)", r'<a href="\2">\1</a>')
    ]
    parts = []
    last_pos = 0
    code_block_pattern = re.compile(r"```(?:\w*)\n([\s\S]*?)\n```", re.MULTILINE | re.DOTALL)
    for match in code_block_pattern.finditer(text):
        start, end = match.span()
        parts.append(escape_html(text[last_pos:start]))
        parts.append(f"<pre>{escape_html(match.group(1))}</pre>")
        last_pos = end
    parts.append(escape_html(text[last_pos:]))
    text = "".join(parts)
    for pattern, replacement in replacements[2:]:
        text = re.sub(pattern, replacement, text, flags=re.MULTILINE | re.DOTALL)
    text = re.sub(r'<!DOCTYPE[^>]*>|<!doctype[^>]*>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<\?[\s\S]*?\?>', '', text)
    return text

@dp.message(Command(commands=["dep"], prefix=BotCommands))
@new_task
@SmartDefender
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
                    bot_response = format_code_response(bot_response)
                else:
                    error_response = await response.text()
                    LOGGER.error(f"DeepSeekAI API request failed with status {response.status}: {error_response}")
                    await Smart_Notify(bot, "dep", f"API request failed with status {response.status}: {error_response}", message)
                    bot_response = "<b>❌ Sorry Bro DeepSeekAI ✨ API Dead</b>"
        if len(bot_response) > 4096:
            await delete_messages(message.chat.id, progress_message.message_id)
            parts = []
            current_part = ""
            for line in bot_response.splitlines(True):
                if len(current_part) + len(line) <= 4096:
                    current_part += line
                else:
                    if current_part:
                        parts.append(current_part)
                    current_part = line
            if current_part:
                parts.append(current_part)
            for part in parts:
                try:
                    await send_message(
                        chat_id=message.chat.id,
                        text=part,
                        parse_mode=ParseMode.HTML
                    )
                    await asyncio.sleep(0.5)
                except TelegramBadRequest as send_e:
                    LOGGER.error(f"Failed to send message part to chat {message.chat.id}: {str(send_e)}")
                    await Smart_Notify(bot, "dep", send_e, message)
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
                await Smart_Notify(bot, "dep", edit_e, message)
                await delete_messages(message.chat.id, progress_message.message_id)
                await send_message(
                    chat_id=message.chat.id,
                    text=bot_response,
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Successfully sent DeepSeekAI response to chat {message.chat.id}")
    except Exception as e:
        LOGGER.error(f"DeepSeekAI error in chat {message.chat.id}: {str(e)}")
        await Smart_Notify(bot, "dep", e, message)
        if progress_message:
            try:
                await progress_message.edit_text(
                    text="<b>❌ Sorry Bro DeepSeekAI ✨ API Dead</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Edited progress message with DeepSeekAI error in chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                await Smart_Notify(bot, "dep", edit_e, message)
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