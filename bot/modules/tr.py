import os
import asyncio
from io import BytesIO
from PIL import Image
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from googletrans import Translator, LANGUAGES
import google.generativeai as genai
from bot import dp
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from config import TRANS_API_KEY, MODEL_NAME, IMGAI_SIZE_LIMIT

DOWNLOAD_DIRECTORY = "./downloads/"

if not os.path.exists(DOWNLOAD_DIRECTORY):
    os.makedirs(DOWNLOAD_DIRECTORY)

translator = Translator()

genai.configure(api_key=TRANS_API_KEY)
model = genai.GenerativeModel(MODEL_NAME)

async def ocr_extract_text(bot: Bot, message: Message):
    photo_path = None
    try:
        LOGGER.info("Starting OCR process...")
        
        if not message.reply_to_message:
            raise ValueError("No reply message found")
            
        if not message.reply_to_message.photo:
            raise ValueError("No photo found in reply message")
        
        LOGGER.info("Downloading image for OCR...")
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

        LOGGER.info("Processing image for OCR with GeminiAI...")
        with Image.open(photo_path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            response = await asyncio.get_event_loop().run_in_executor(None, lambda: model.generate_content(["Extract only the main text from this image, ignoring any labels or additional comments, and return it as plain text", img]))
            text = response.text
            if not text:
                LOGGER.warning("No text extracted from image")
                return ""
            else:
                LOGGER.info("Successfully extracted text from image")
                return text.strip()

    except Exception as e:
        LOGGER.error(f"OCR Error: {e}")
        await Smart_Notify(bot, "tr ocr", e, message)
        raise
    finally:
        if photo_path and os.path.exists(photo_path):
            clean_download(photo_path)

def translate_text(text, target_lang):
    try:
        if not text or not text.strip():
            raise ValueError("Empty text provided for translation")
        translation = translator.translate(text, dest=target_lang)
        LOGGER.info(f"Translated text to {target_lang}")
        return translation.text
    except Exception as e:
        LOGGER.error(f"Translation error: {e}")
        raise

async def format_text(text):
    if not text:
        return ""
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n'.join(lines)

@dp.message(Command(commands=["tr"] + [f"tr{code}" for code in LANGUAGES.keys()], prefix=BotCommands))
@new_task
async def tr_handler(message: Message, bot: Bot):
    LOGGER.info(f"Received /tr command from user: {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
    loading_message = None
    try:
        cmd = message.text.split()[0][1:].lower()
        combined_format = len(cmd) > 2 and cmd[2:] in LANGUAGES
        photo_mode = message.reply_to_message and message.reply_to_message.photo
        text_mode = (message.reply_to_message and message.reply_to_message.text) or (get_args(message) and not combined_format) or (combined_format and len(get_args(message)) > 0)

        if combined_format:
            target_lang = cmd[2:]
            text_to_translate = " ".join(get_args(message)) if not (photo_mode or (message.reply_to_message and message.reply_to_message.text)) else None
        else:
            args = get_args(message)
            if not args:
                loading_message = await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Invalid Language Code!</b>",
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
                LOGGER.warning(f"Invalid command format: {message.text}")
                return
            target_lang = args[0].lower()
            text_to_translate = " ".join(args[1:]) if not (photo_mode or (message.reply_to_message and message.reply_to_message.text)) else None

        if target_lang not in LANGUAGES:
            loading_message = await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Invalid Language Code!</b>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            LOGGER.warning(f"Invalid language code: {target_lang}")
            return

        if text_mode and not photo_mode:
            text_to_translate = message.reply_to_message.text if message.reply_to_message and message.reply_to_message.text else text_to_translate
            if not text_to_translate:
                loading_message = await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ No Text Provided To Translate!</b>",
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
                LOGGER.warning("No text provided for translation")
                return
        elif photo_mode:
            if not message.reply_to_message or not message.reply_to_message.photo:
                loading_message = await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Reply To A Valid Photo For Translation!</b>",
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
                LOGGER.warning("No valid photo provided for OCR")
                return
        else:
            loading_message = await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Provide Text Or Reply To A Photo!</b>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            LOGGER.warning("No valid input provided for translation")
            return

        loading_message = await send_message(
            chat_id=message.chat.id,
            text=f"<b>Translating Your {'Image' if photo_mode else 'Text'} Into {LANGUAGES[target_lang].capitalize()}...</b>",
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
                        LOGGER.warning("No valid text extracted from image")
                        return
                    except TelegramBadRequest as edit_e:
                        LOGGER.error(f"Failed to edit loading message in chat {message.chat.id}: {str(edit_e)}")
                        await send_message(
                            chat_id=message.chat.id,
                            text="<b>❌ No Readable Text Found In The Image</b>",
                            parse_mode=ParseMode.HTML
                        )
                        return
                text_to_translate = extracted_text
            except Exception as ocr_error:
                LOGGER.error(f"OCR failed: {ocr_error}")
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
            initial_translation = translate_text(text_to_translate, 'en')
            translated_text = translate_text(initial_translation, target_lang)
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
            LOGGER.info(f"Sent translation to {target_lang} in chat {message.chat.id}")

        except Exception as trans_error:
            LOGGER.error(f"Translation failed: {trans_error}")
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
        LOGGER.error(f"Translation handler error: {str(e)}")
        await Smart_Notify(bot, "tr", e, message)
        error_text = "<b>❌ Sorry, Translation Service Is Currently Unavailable</b>"
        if loading_message:
            try:
                await loading_message.edit_text(
                    text=error_text,
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Edited loading message with error in chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit loading message in chat {message.chat.id}: {str(edit_e)}")
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
        LOGGER.info(f"Sent error message to chat {message.chat.id}")