import os
import asyncio
from io import BytesIO
from PIL import Image
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
import google.generativeai as genai
from bot import dp
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.defend import SmartDefender
from config import A360APIBASEURL, MODEL_NAME, IMGAI_SIZE_LIMIT, TRANS_API_KEY
import aiohttp

DOWNLOAD_DIRECTORY = "./downloads/"
if not os.path.exists(DOWNLOAD_DIRECTORY):
    os.makedirs(DOWNLOAD_DIRECTORY)

genai.configure(api_key=TRANS_API_KEY)
model = genai.GenerativeModel(MODEL_NAME)

async def ocr_extract_text(bot: Bot, message: Message):
    photo_path = None
    try:
        if not message.reply_to_message:
            raise ValueError("No reply message found")
        if not message.reply_to_message.photo:
            raise ValueError("No photo found in reply message")
        photo = message.reply_to_message.photo[-1]
        filename = f"ocr_temp_{message.message_id}_{photo.file_id}.jpg"
        photo_path = os.path.join(DOWNLOAD_DIRECTORY, filename)
        try:
            file_info = await bot.get_file(photo.file_id)
            if not file_info.file_path:
                raise ValueError("Could not get file path from Telegram")
            await bot.download_file(file_info.file_path, photo_path)
        except (TelegramNetworkError, TimeoutError) as e:
            raise ValueError(f"Failed to download image: {str(e)}")
        except Exception as e:
            raise ValueError(f"Download error: {str(e)}")
        if not os.path.exists(photo_path):
            raise ValueError("Downloaded file does not exist")
        if os.path.getsize(photo_path) == 0:
            raise ValueError("Downloaded file is empty")
        if os.path.getsize(photo_path) > IMGAI_SIZE_LIMIT:
            raise ValueError(f"Image too large. Max {IMGAI_SIZE_LIMIT/1000000}MB allowed")
        with Image.open(photo_path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            response = await asyncio.get_event_loop().run_in_executor(None, lambda: model.generate_content(["Extract only the main text from this image, ignoring any labels or additional comments, and return it as plain text", img]))
            text = response.text
            if not text:
                return ""
            else:
                return text.strip()
    except Exception as e:
        await Smart_Notify(bot, "tr ocr", e, message)
        raise
    finally:
        if photo_path and os.path.exists(photo_path):
            clean_download(photo_path)

async def translate_text(text, target_lang):
    try:
        if not text or not text.strip():
            raise ValueError("Empty text provided for translation")
        async with aiohttp.ClientSession() as session:
            url = f"{A360APIBASEURL}/tr"
            params = {"text": text, "lang": target_lang}
            async with session.get(url, params=params) as resp:
                if resp.status != 200:
                    raise ValueError(f"API error: {resp.status}")
                data = await resp.json()
                return data.get("translated_text", "")
    except Exception as e:
        raise

async def format_text(text):
    if not text:
        return ""
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n'.join(lines)

@dp.message(Command(commands=["tr"], prefix=BotCommands))
@new_task
@SmartDefender
async def tr_handler(message: Message, bot: Bot):
    loading_message = None
    try:
        args = get_args(message)
        if not args:
            loading_message = await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Invalid Usage! Use /tr <lang_code> [text] or reply</b>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            return
        target_lang = args[0].lower()
        photo_mode = message.reply_to_message and message.reply_to_message.photo
        text_mode = (message.reply_to_message and message.reply_to_message.text) or (len(args) > 1)
        text_to_translate = None
        if text_mode and not photo_mode:
            text_to_translate = message.reply_to_message.text if message.reply_to_message and message.reply_to_message.text else " ".join(args[1:])
            if not text_to_translate:
                loading_message = await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ No Text Provided To Translate!</b>",
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
                return
        elif photo_mode:
            if not message.reply_to_message or not message.reply_to_message.photo:
                loading_message = await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Reply To A Valid Photo For Translation!</b>",
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
                return
        else:
            loading_message = await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Provide Text Or Reply To A Photo!</b>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            return
        loading_message = await send_message(
            chat_id=message.chat.id,
            text=f"<b>Translating Your {'Image' if photo_mode else 'Text'}...</b>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        if photo_mode:
            try:
                extracted_text = await ocr_extract_text(bot, message)
                if not extracted_text or not extracted_text.strip():
                    try:
                        await loading_message.edit_text(
                            text="<b>❌ No Readable Text Found In The Image</b>",
                            parse_mode=ParseMode.HTML
                        )
                        return
                    except TelegramBadRequest as edit_e:
                        await send_message(
                            chat_id=message.chat.id,
                            text="<b>❌ No Readable Text Found In The Image</b>",
                            parse_mode=ParseMode.HTML
                        )
                        return
                text_to_translate = extracted_text
            except Exception as ocr_error:
                try:
                    await loading_message.edit_text(
                        text="<b>❌ Failed To Process Image. Please Try Again.</b>",
                        parse_mode=ParseMode.HTML
                    )
                except TelegramBadRequest:
                    await send_message(
                        chat_id=message.chat.id,
                        text="<b>❌ Failed To Process Image. Please Try Again.</b>",
                        parse_mode=ParseMode.HTML
                    )
                return
        try:
            translated_text = await translate_text(text_to_translate, target_lang)
            formatted_text = await format_text(translated_text)
            if not formatted_text:
                raise ValueError("Translation resulted in empty text")
            if len(formatted_text) > 4000:
                await delete_messages(message.chat.id, loading_message.message_id)
                parts = [formatted_text[i:i+4000] for i in range(0, len(formatted_text), 4000)]
                for part in parts:
                    await send_message(
                        chat_id=message.chat.id,
                        text=part,
                        parse_mode=ParseMode.HTML
                    )
            else:
                await loading_message.edit_text(
                    text=formatted_text,
                    parse_mode=ParseMode.HTML
                )
        except Exception as trans_error:
            try:
                await loading_message.edit_text(
                    text="<b>❌ Translation Failed. Please Try Again.</b>",
                    parse_mode=ParseMode.HTML
                )
            except TelegramBadRequest:
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Translation Failed. Please Try Again.</b>",
                    parse_mode=ParseMode.HTML
                )
    except Exception as e:
        await Smart_Notify(bot, "tr", e, message)
        error_text = "<b>❌ Sorry, Translation Service Is Currently Unavailable</b>"
        if loading_message:
            try:
                await loading_message.edit_text(
                    text=error_text,
                    parse_mode=ParseMode.HTML
                )
            except TelegramBadRequest as edit_e:
                await Smart_Notify(bot, "tr", edit_e, message)
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