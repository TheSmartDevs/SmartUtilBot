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
from bot.helpers.defend import SmartDefender
from config import OCR_API_KEY, MODEL_NAME, IMGAI_SIZE_LIMIT
import re
import asyncio
import pygments
from pygments.lexers import get_lexer_by_name, guess_lexer
from pygments.formatters import HtmlFormatter
import os

logger = LOGGER
genai.configure(api_key=OCR_API_KEY)
model = genai.GenerativeModel(MODEL_NAME)

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
    code_block_pattern = re.compile(r"```(\w*)\n([\s\S]*?)\n```", re.MULTILINE | re.DOTALL)

    try:
        lexer = guess_lexer(text)
        lang = lexer.name.lower()
        formatted_code = pygments.highlight(text, lexer, HtmlFormatter(nowrap=True))
        formatted_code = re.sub(r'<span[^>]*>(.*?)</span>', r'\1', formatted_code)
        return f"<pre>{formatted_code}</pre>"
    except:
        pass

    for match in code_block_pattern.finditer(text):
        start, end = match.span()
        lang = match.group(1).lower() or None
        code = match.group(2)

        parts.append(escape_html(text[last_pos:start]))

        if not lang:
            try:
                lexer = guess_lexer(code)
                lang = lexer.name.lower()
            except:
                lang = None

        if lang:
            try:
                lexer = get_lexer_by_name(lang, stripall=True)
                formatted_code = pygments.highlight(code, lexer, HtmlFormatter(nowrap=True))
                formatted_code = re.sub(r'<span[^>]*>(.*?)</span>', r'\1', formatted_code)
                parts.append(f"<pre>{formatted_code}</pre>")
            except:
                parts.append(f"<pre>{escape_html(code)}</pre>")
        else:
            parts.append(f"<pre>{escape_html(code)}</pre>")

        last_pos = end

    parts.append(escape_html(text[last_pos:]))
    text = "".join(parts)

    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.MULTILINE | re.DOTALL)

    text = re.sub(r'<!DOCTYPE[^>]*>|<!doctype[^>]*>', '', text, flags=re.IGNORECASE)
    text = re.sub(r'<\?[\s\S]*?\?>', '', text)

    return text

@dp.message(Command(commands=["ocr"], prefix=BotCommands))
@new_task
@SmartDefender
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
    user_full_name = message.from_user.full_name
    logger.info(f"OCR Command Received From User {user_full_name} [{user_id}]")

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
        photo_file = message.reply_to_message.photo[-1]
        file_serial = f"{message.message_id}"
        photo_path = f"downloads/ocr_temp_{file_serial}.jpg"
        os.makedirs("downloads", exist_ok=True)
        logger.info(f"Downloading Photo: downloads/ocr_temp_{file_serial}")

        if photo_file.file_size > IMGAI_SIZE_LIMIT:
            raise ValueError(f"Image too large. Max {IMGAI_SIZE_LIMIT/1000000}MB allowed")

        await bot.download(
            file=photo_file,
            destination=photo_path
        )

        logger.info(f"Processing OCR: downloads/ocr_temp_{file_serial}")
        with Image.open(photo_path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            response = model.generate_content(["Extract text from this image of all lang Just Send The Extracted Text No Extra Text Or Hi Hello", img])
            text = response.text
            logger.info(f"OCR Response: {text}")

            response_text = text if text else "<b>❌ No readable text found in image.</b>"
            formatted_text = format_code_response(response_text)
            if len(formatted_text) > 4096:
                await delete_messages(
                    chat_id=message.chat.id,
                    message_ids=[processing_msg.message_id]
                )
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
                            parse_mode=ParseMode.HTML,
                            disable_web_page_preview=True
                        )
                        await asyncio.sleep(0.5)
                    except TelegramBadRequest as send_e:
                        logger.error(f"Failed to send message part to chat {message.chat.id}: {str(send_e)}")
                        await Smart_Notify(bot, "ocr", send_e, message)
                logger.info(f"Successfully sent OCR response (split) to chat {message.chat.id}")
            else:
                try:
                    await processing_msg.edit_text(
                        text=formatted_text,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True
                    )
                    logger.info(f"Successfully sent OCR response to chat {message.chat.id}")
                except Exception as edit_e:
                    logger.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                    await Smart_Notify(bot, "ocr", edit_e, message)
                    await delete_messages(
                        chat_id=message.chat.id,
                        message_ids=[processing_msg.message_id]
                    )
                    await send_message(
                        chat_id=message.chat.id,
                        text=formatted_text,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True
                    )
                    logger.info(f"Successfully sent OCR response to chat {message.chat.id}")

    except Exception as e:
        logger.error(f"OCR Error: {str(e)}")
        await Smart_Notify(bot, "ocr", e, message)
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
            logger.info(f"Cleaning Download: downloads/ocr_temp_{file_serial}")
            clean_download(photo_path)