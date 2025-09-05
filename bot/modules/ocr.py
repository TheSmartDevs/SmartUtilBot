import google.generativeai as genai
from PIL import Image
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode, ChatType
from bot import dp, SmartAIO
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages
from bot.helpers.notify import Smart_Notify
from bot.helpers.logger import LOGGER
from bot.helpers.commands import BotCommands
from config import OCR_API_KEY, MODEL_NAME, IMGAI_SIZE_LIMIT

logger = LOGGER

genai.configure(api_key=OCR_API_KEY)
model = genai.GenerativeModel(MODEL_NAME)

@dp.message(Command(commands=["ocr"], prefix=BotCommands))
@new_task
async def ocr_handler(message: Message, bot: Bot):
    if message.chat.type not in [ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP]:
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ This command only works in private or group chats</b>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        return
    user_id = message.from_user.id
    logger.info(f"Command received from user {user_id} in chat {message.chat.id}: {message.text}")
    if not message.reply_to_message or not message.reply_to_message.photo:
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Please reply to a photo to extract text.</b>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        return
    processing_msg = await send_message(
        chat_id=message.chat.id,
        text="<b>Processing Your Request...✨</b>",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )
    photo_path = None
    try:
        logger.info("Downloading image...")
        photo_file = message.reply_to_message.photo[-1]
        if photo_file.file_size > IMGAI_SIZE_LIMIT:
            raise ValueError(f"Image too large. Max {IMGAI_SIZE_LIMIT/1000000}MB allowed")
        photo_path = f"ocr_temp_{message.message_id}.jpg"
        await bot.download(
            file=photo_file,
            destination=photo_path
        )
        logger.info("Processing image for OCR with GeminiAI...")
        with Image.open(photo_path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            response = model.generate_content(["Extract text from this image of all lang Just Send The Extracted Text No Extra Text Or Hi Hello", img])
            text = response.text
            logger.info(f"OCR Response: {text}")
            response_text = text if text else "<b>❌ No readable text found in image.</b>"
            try:
                await processing_msg.edit_text(
                    text=response_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
            except Exception:
                await delete_messages(
                    chat_id=message.chat.id,
                    message_ids=[processing_msg.message_id]
                )
                await send_message(
                    chat_id=message.chat.id,
                    text=response_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
    except Exception as e:
        logger.error(f"OCR Error: {str(e)}")
        await Smart_Notify(bot, "/ocr", e, message)
        try:
            await processing_msg.edit_text(
                text="<b>❌ Sorry Bro OCR API Dead</b>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        except Exception:
            await delete_messages(
                chat_id=message.chat.id,
                message_ids=[processing_msg.message_id]
            )
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Sorry Bro OCR API Dead</b>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
    finally:
        if photo_path:
            clean_download(photo_path)
            logger.info(f"Deleted temporary image file: {photo_path}")