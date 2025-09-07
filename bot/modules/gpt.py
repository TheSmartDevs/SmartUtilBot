# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
#  Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
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
            "max_tokens": 500,
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
            if len(response_text) > 4000:
                await delete_messages(message.chat.id, progress_message.message_id)
                parts = [response_text[i:i+4000] for i in range(0, len(response_text), 4000)]
                for part in parts:
                    await send_message(
                        chat_id=message.chat.id,
                        text=part,
                        parse_mode=ParseMode.HTML
                    )
                LOGGER.info(f"Successfully sent GPT response (split) to chat {message.chat.id}")
            else:
                try:
                    await progress_message.edit_text(
                        text=response_text,
                        parse_mode=ParseMode.HTML
                    )
                    LOGGER.info(f"Successfully sent GPT response to chat {message.chat.id}")
                except TelegramBadRequest as edit_e:
                    LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                    await Smart_Notify(bot, "gpt", edit_e, message)
                    await delete_messages(message.chat.id, progress_message.message_id)
                    await send_message(
                        chat_id=message.chat.id,
                        text=response_text,
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