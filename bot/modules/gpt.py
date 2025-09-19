import aiohttp
import asyncio
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
from config import OPENAI_API_KEY
import re

async def fetch_gpt_response(prompt, model):
    if not OPENAI_API_KEY or OPENAI_API_KEY.strip() == "":
        LOGGER.error("OpenAI API key is missing or invalid")
        return None
    async with aiohttp.ClientSession() as session:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1500,
            "n": 1,
            "stop": None,
            "temperature": 0.5
        }
        try:
            async with session.post(url, headers=headers, json=data) as response:
                if response.status == 200:
                    json_response = await response.json()
                    response_text = json_response['choices'][0]['message']['content']
                    LOGGER.info(f"Successfully fetched GPT response for prompt: {prompt[:50]}...")
                    return response_text
                else:
                    error_response = await response.text()
                    LOGGER.error(f"OpenAI API returned status {response.status}: {error_response}")
                    return None
        except Exception as e:
            LOGGER.error(f"Error fetching GPT response: {e}")
            return None

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
    for pattern, replacement in replacements[2:]:  # Skip code block replacement
        text = re.sub(pattern, replacement, text, flags=re.MULTILINE | re.DOTALL)
    text = re.sub(r'<!DOCTYPE[^>]*>|<!doctype[^>]*>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<\?[\s\S]*?\?>', '', text)
    return text

@dp.message(Command(commands=["gpt4"], prefix=BotCommands))
@new_task
@SmartDefender
async def gpt4_handler(message: Message, bot: Bot):
    LOGGER.info(f"Received command: '{message.text}' from user {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
    progress_message = None
    try:
        progress_message = await send_message(
            chat_id=message.chat.id,
            text="<b>GPT-4 Gate Off 🔕</b>",
            parse_mode=ParseMode.HTML
        )
        LOGGER.info(f"Successfully sent GPT-4 gate off message to chat {message.chat.id}")
    except Exception as e:
        LOGGER.error(f"Failed to send GPT-4 gate off message to chat {message.chat.id}: {str(e)}")
        await Smart_Notify(bot, "gpt4", e, message)
        if progress_message:
            try:
                await progress_message.edit_text(
                    text="<b>❌ Sorry Bro GPT-4 API Error</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Edited progress message with GPT-4 error in chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                await Smart_Notify(bot, "gpt4", edit_e, message)
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Sorry Bro GPT-4 API Error</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Sent GPT-4 error message to chat {message.chat.id}")
        else:
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Sorry Bro GPT-4 API Error</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Sent GPT-4 error message to chat {message.chat.id}")

@dp.message(Command(commands=["gpt", "gpt3", "gpt3.5"], prefix=BotCommands))
@new_task
@SmartDefender
async def gpt_handler(message: Message, bot: Bot):
    LOGGER.info(f"Received command: '{message.text}' from user {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
    progress_message = None
    try:
        progress_message = await send_message(
            chat_id=message.chat.id,
            text="<b>ChatGPT 3.5 Is Thinking ✨</b>",
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
                text="<b>Please Provide A Prompt For ChatGPT AI ✨ Response</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Prompt missing for GPT command in chat {message.chat.id}")
            return
        await asyncio.sleep(1)
        response_text = await fetch_gpt_response(prompt, "gpt-4o-mini")
        if response_text:
            formatted_text = format_code_response(response_text)
            if len(formatted_text) > 4096:
                await delete_messages(message.chat.id, progress_message.message_id)
                parts = []
                current_part = ""
                for line in formatted_text.splitlines(True):
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
                        await asyncio.sleep(0.5)  # Avoid rate limits
                    except TelegramBadRequest as send_e:
                        LOGGER.error(f"Failed to send message part to chat {message.chat.id}: {str(send_e)}")
                        await Smart_Notify(bot, "gpt", send_e, message)
                LOGGER.info(f"Successfully sent GPT response (split) to chat {message.chat.id}")
            else:
                try:
                    await progress_message.edit_text(
                        text=formatted_text,
                        parse_mode=ParseMode.HTML
                    )
                    LOGGER.info(f"Successfully sent GPT response to chat {message.chat.id}")
                except TelegramBadRequest as edit_e:
                    LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                    await Smart_Notify(bot, "gpt", edit_e, message)
                    await delete_messages(message.chat.id, progress_message.message_id)
                    await send_message(
                        chat_id=message.chat.id,
                        text=formatted_text,
                        parse_mode=ParseMode.HTML
                    )
                    LOGGER.info(f"Successfully sent GPT response to chat {message.chat.id}")
        else:
            try:
                await progress_message.edit_text(
                    text="<b>Sorry Chat GPT 3.5 API Dead</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Edited progress message with GPT error in chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                await Smart_Notify(bot, "gpt", edit_e, message)
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>Sorry Chat GPT 3.5 API Dead</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Sent GPT error message to chat {message.chat.id}")
    except Exception as e:
        LOGGER.error(f"Error processing GPT command in chat {message.chat.id}: {str(e)}")
        await Smart_Notify(bot, "gpt", e, message)
        if progress_message:
            try:
                await progress_message.edit_text(
                    text="<b>Sorry Chat GPT 3.5 API Dead</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Edited progress message with GPT error in chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                await Smart_Notify(bot, "gpt", edit_e, message)
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>Sorry Chat GPT 3.5 API Dead</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Sent GPT error message to chat {message.chat.id}")
        else:
            await send_message(
                chat_id=message.chat.id,
                text="<b>Sorry Chat GPT 3.5 API Dead</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Sent GPT error message to chat {message.chat.id}")