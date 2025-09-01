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
from config import GOOGLE_API_KEY, MODEL_NAME, IMGAI_SIZE_LIMIT
import google.generativeai as genai
from PIL import Image
import os
import asyncio

genai.configure(api_key=GOOGLE_API_KEY)
model = genai.GenerativeModel(MODEL_NAME)

@dp.message(Command(commands=["gem", "gemi", "gemini"], prefix=BotCommands))
@new_task
async def gemi_handler(message: Message, bot: Bot):
    LOGGER.info(f"Received command: '{message.text}' from user {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
    progress_message = None
    try:
        progress_message = await send_message(
            chat_id=message.chat.id,
            text="<b>🔍 GeminiAI is thinking, Please Wait ✨</b>",
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
                text="<b>Please Provide A Prompt For GeminiAI ✨ Response</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Prompt missing for Gemini command in chat {message.chat.id}")
            return

        response = model.generate_content(prompt)
        response_text = response.text

        if len(response_text) > 4000:
            await delete_messages(message.chat.id, progress_message.message_id)
            parts = [response_text[i:i+4000] for i in range(0, len(response_text), 4000)]
            for part in parts:
                await send_message(
                    chat_id=message.chat.id,
                    text=part,
                    parse_mode=ParseMode.HTML
                )
            LOGGER.info(f"Successfully sent Gemini response (split) to chat {message.chat.id}")
        else:
            try:
                await progress_message.edit_text(
                    text=response_text,
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Successfully sent Gemini response to chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                await delete_messages(message.chat.id, progress_message.message_id)
                await send_message(
                    chat_id=message.chat.id,
                    text=response_text,
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Successfully sent Gemini response to chat {message.chat.id}")
    except Exception as e:
        LOGGER.error(f"Gemini error in chat {message.chat.id}: {str(e)}")
        if progress_message:
            try:
                await progress_message.edit_text(
                    text="<b>❌ Sorry Bro Gemini API Error</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Edited progress message with Gemini error in chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Sorry Bro Gemini API Error</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Sent Gemini error message to chat {message.chat.id}")
        else:
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Sorry Bro Gemini API Error</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Sent Gemini error message to chat {message.chat.id}")

@dp.message(Command(commands=["imgai"], prefix=BotCommands))
@new_task
async def imgai_handler(message: Message, bot: Bot):
    LOGGER.info(f"Received command: '{message.text}' from user {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
    progress_message = None
    try:
        if not message.reply_to_message or not message.reply_to_message.photo:
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Please Reply To An Image For Analysis</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"No image replied for imgai command in chat {message.chat.id}")
            return

        progress_message = await send_message(
            chat_id=message.chat.id,
            text="<b>🔍 Gemini Is Analyzing The Image Please Wait ✨</b>",
            parse_mode=ParseMode.HTML
        )

        photo = message.reply_to_message.photo[-1]
        photo_path = f"temp_{message.chat.id}_{photo.file_id}.jpg"
        try:
            await bot.download(file=photo, destination=photo_path)
            if os.path.getsize(photo_path) > IMGAI_SIZE_LIMIT:
                await progress_message.edit_text(
                    text="<b>❌ Sorry Bro Image Too Large</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Image too large for imgai in chat {message.chat.id}")
                return

            with Image.open(photo_path) as img:
                if img.mode != 'RGB':
                    img = img.convert('RGB')
            command_text = message.text.split(maxsplit=1)
            user_prompt = command_text[1] if len(command_text) > 1 else "Describe this image in detail"
            response = model.generate_content([user_prompt, img])
            analysis = response.text

            if len(analysis) > 4000:
                await delete_messages(message.chat.id, progress_message.message_id)
                parts = [analysis[i:i+4000] for i in range(0, len(analysis), 4000)]
                for part in parts:
                    await send_message(
                        chat_id=message.chat.id,
                        text=part,
                        parse_mode=ParseMode.HTML
                    )
                LOGGER.info(f"Successfully sent imgai response (split) to chat {message.chat.id}")
            else:
                try:
                    await progress_message.edit_text(
                        text=analysis,
                        parse_mode=ParseMode.HTML
                    )
                    LOGGER.info(f"Successfully sent imgai response to chat {message.chat.id}")
                except TelegramBadRequest as edit_e:
                    LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                    await delete_messages(message.chat.id, progress_message.message_id)
                    await send_message(
                        chat_id=message.chat.id,
                        text=analysis,
                        parse_mode=ParseMode.HTML
                    )
                    LOGGER.info(f"Successfully sent imgai response to chat {message.chat.id}")
        except Exception as e:
            LOGGER.error(f"Image analysis error in chat {message.chat.id}: {str(e)}")
            if progress_message:
                try:
                    await progress_message.edit_text(
                        text="<b>❌ Sorry Bro ImageAI Error</b>",
                        parse_mode=ParseMode.HTML
                    )
                    LOGGER.info(f"Edited progress message with imgai error in chat {message.chat.id}")
                except TelegramBadRequest as edit_e:
                    LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                    await send_message(
                        chat_id=message.chat.id,
                        text="<b>❌ Sorry Bro ImageAI Error</b>",
                        parse_mode=ParseMode.HTML
                    )
                    LOGGER.info(f"Sent imgai error message to chat {message.chat.id}")
            else:
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Sorry Bro ImageAI Error</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Sent imgai error message to chat {message.chat.id}")
        finally:
            if os.path.exists(photo_path):
                os.remove(photo_path)
    except Exception as e:
        LOGGER.error(f"Image analysis error in chat {message.chat.id}: {str(e)}")
        if progress_message:
            try:
                await progress_message.edit_text(
                    text="<b>❌ Sorry Bro ImageAI Error</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Edited progress message with imgai error in chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Sorry Bro ImageAI Error</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Sent imgai error message to chat {message.chat.id}")
        else:
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Sorry Bro ImageAI Error</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Sent imgai error message to chat {message.chat.id}")