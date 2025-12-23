#Copyright @ISmartCoder
#Updates Channel @abirxdhackz
import os
import asyncio
import base64
import binascii
import codecs
import urllib.parse
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ParseMode
from bot import dp
from bot.helpers.utils import new_task
from bot.helpers.botutils import send_message, delete_messages
from bot.helpers.buttons import SmartButtons
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.defend import SmartDefender
from config import COMMAND_PREFIX

encoders = {
    "base32": lambda text: base64.b32encode(text.encode()).decode(),
    "base64": lambda text: base64.b64encode(text.encode()).decode(),
    "base85": lambda text: base64.b85encode(text.encode()).decode(),
    "ascii85": lambda text: base64.a85encode(text.encode()).decode(),
    "binary": lambda text: ' '.join(format(ord(char), '08b') for char in text),
    "hexadecimal": lambda text: binascii.hexlify(text.encode()).decode(),
    "octal": lambda text: ' '.join(format(ord(char), '03o') for char in text),
    "unicode": lambda text: ' '.join(f'U+{ord(char):04X}' for char in text),
    "rot13": lambda text: codecs.encode(text, 'rot_13'),
    "url": lambda text: urllib.parse.quote(text)
}

decoders = {
    "base32": lambda text: base64.b32decode(text).decode(),
    "base64": lambda text: base64.b64decode(text).decode(),
    "base85": lambda text: base64.b85decode(text).decode(),
    "ascii85": lambda text: base64.a85decode(text).decode(),
    "binary": lambda text: ''.join(chr(int(b, 2)) for b in text.split()),
    "hexadecimal": lambda text: binascii.unhexlify(text).decode(),
    "octal": lambda text: ''.join(chr(int(o, 8)) for o in text.split()),
    "unicode": lambda text: ''.join(chr(int(code.replace('U+', ''), 16)) for code in text.split()),
    "rot13": lambda text: codecs.decode(text, 'rot_13'),
    "url": lambda text: urllib.parse.unquote(text)
}

text_transformers = {
    "uppercase": lambda text: text.upper(),
    "lowercase": lambda text: text.lower(),
    "capitalize": lambda text: text.capitalize(),
    "titlecase": lambda text: text.title(),
    "reverse": lambda text: text[::-1],
    "swapcase": lambda text: text.swapcase()
}

def get_encoder_keyboard():
    buttons = SmartButtons()
    buttons.button("Base 32", callback_data="encoder:base32")
    buttons.button("Base 64", callback_data="encoder:base64")
    buttons.button("Base 85", callback_data="encoder:base85")
    buttons.button("ASCII85", callback_data="encoder:ascii85")
    buttons.button("Binary", callback_data="encoder:binary")
    buttons.button("Hexadecimal", callback_data="encoder:hexadecimal")
    buttons.button("Octal", callback_data="encoder:octal")
    buttons.button("Unicode", callback_data="encoder:unicode")
    buttons.button("ROT13", callback_data="encoder:rot13")
    buttons.button("URL", callback_data="encoder:url")
    buttons.button("❌ Close", callback_data="close_menu", position="footer")
    return buttons.build_menu(b_cols=2, f_cols=1)

def get_decoder_keyboard():
    buttons = SmartButtons()
    buttons.button("Base 32", callback_data="decoder:base32")
    buttons.button("Base 64", callback_data="decoder:base64")
    buttons.button("Base 85", callback_data="decoder:base85")
    buttons.button("ASCII85", callback_data="decoder:ascii85")
    buttons.button("Binary", callback_data="decoder:binary")
    buttons.button("Hexadecimal", callback_data="decoder:hexadecimal")
    buttons.button("Octal", callback_data="decoder:octal")
    buttons.button("Unicode", callback_data="decoder:unicode")
    buttons.button("ROT13", callback_data="decoder:rot13")
    buttons.button("URL", callback_data="decoder:url")
    buttons.button("❌ Close", callback_data="close_menu", position="footer")
    return buttons.build_menu(b_cols=2, f_cols=1)

def get_text_keyboard():
    buttons = SmartButtons()
    buttons.button("UPPERCASE", callback_data="texttransform:uppercase")
    buttons.button("lowercase", callback_data="texttransform:lowercase")
    buttons.button("Capitalize", callback_data="texttransform:capitalize")
    buttons.button("Title Case", callback_data="texttransform:titlecase")
    buttons.button("Reverse", callback_data="texttransform:reverse")
    buttons.button("SWAPcASE", callback_data="texttransform:swapcase")
    buttons.button("❌ Close", callback_data="close_menu", position="footer")
    return buttons.build_menu(b_cols=2, f_cols=1)

def extract_input_text(message_text: str) -> str | None:
    if not message_text:
        return None
    if "<code>" not in message_text or "</code>" not in message_text:
        return None
    start = message_text.find("<code>") + 6
    end = message_text.find("</code>", start)
    if end == -1:
        return None
    extracted = message_text[start:end]
    if extracted.strip() == "":
        return None
    return extracted

@dp.message(Command(commands=["en"], prefix=COMMAND_PREFIX))
@new_task
@SmartDefender
async def encode_command(message: Message, bot: Bot):
    processing_msg = None
    try:
        LOGGER.info(f"Processing /en command from user {message.from_user.id} in chat {message.chat.id}")
        processing_msg = await send_message(
            chat_id=message.chat.id,
            text="<b>Processing Your Input...✨</b>",
            parse_mode=ParseMode.HTML
        )
        text = None
        if message.reply_to_message and message.reply_to_message.text:
            text = message.reply_to_message.text
            LOGGER.info(f"Text taken from reply: {text[:100]}...")
        elif len(message.text.split(maxsplit=1)) > 1:
            text = message.text.split(maxsplit=1)[1]
            LOGGER.info(f"Text taken from command args: {text[:100]}...")
        if not text:
            await processing_msg.edit_text(
                text="<b>⚠️ Please provide text or reply to a message❌</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.warning(f"No text provided for /en by user {message.from_user.id}")
            return
        response_text = f"<b>Inputed Text:</b>\n\n<code>{text}</code>"
        await processing_msg.edit_text(
            text=response_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_encoder_keyboard()
        )
        LOGGER.info(f"Encoder menu sent successfully for /en")
    except Exception as e:
        LOGGER.error(f"Error in /en command: {str(e)}", exc_info=True)
        if processing_msg:
            try:
                await processing_msg.edit_text(
                    text="<b>❌ Sorry Bro, Invalid Text Provided!</b>",
                    parse_mode=ParseMode.HTML
                )
            except:
                pass
        await Smart_Notify(bot, "/en", e, message)

@dp.message(Command(commands=["de"], prefix=COMMAND_PREFIX))
@new_task
@SmartDefender
async def decode_command(message: Message, bot: Bot):
    processing_msg = None
    try:
        LOGGER.info(f"Processing /de command from user {message.from_user.id} in chat {message.chat.id}")
        processing_msg = await send_message(
            chat_id=message.chat.id,
            text="<b>Processing Your Input...✨</b>",
            parse_mode=ParseMode.HTML
        )
        text = None
        if message.reply_to_message and message.reply_to_message.text:
            text = message.reply_to_message.text
            LOGGER.info(f"Text taken from reply: {text[:100]}...")
        elif len(message.text.split(maxsplit=1)) > 1:
            text = message.text.split(maxsplit=1)[1]
            LOGGER.info(f"Text taken from command args: {text[:100]}...")
        if not text:
            await processing_msg.edit_text(
                text="<b>⚠️ Please provide text or reply to a message❌</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.warning(f"No text provided for /de by user {message.from_user.id}")
            return
        response_text = f"<b>Inputed Text:</b>\n\n<code>{text}</code>"
        await processing_msg.edit_text(
            text=response_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_decoder_keyboard()
        )
        LOGGER.info(f"Decoder menu sent successfully for /de")
    except Exception as e:
        LOGGER.error(f"Error in /de command: {str(e)}", exc_info=True)
        if processing_msg:
            try:
                await processing_msg.edit_text(
                    text="<b>❌ Sorry Bro, Invalid Text Provided!</b>",
                    parse_mode=ParseMode.HTML
                )
            except:
                pass
        await Smart_Notify(bot, "/de", e, message)

@dp.message(Command(commands=["text"], prefix=COMMAND_PREFIX))
@new_task
@SmartDefender
async def text_command(message: Message, bot: Bot):
    processing_msg = None
    try:
        LOGGER.info(f"Processing /text command from user {message.from_user.id} in chat {message.chat.id}")
        processing_msg = await send_message(
            chat_id=message.chat.id,
            text="<b>Processing Your Input...✨</b>",
            parse_mode=ParseMode.HTML
        )
        text = None
        if message.reply_to_message and message.reply_to_message.text:
            text = message.reply_to_message.text
            LOGGER.info(f"Text taken from reply: {text[:100]}...")
        elif len(message.text.split(maxsplit=1)) > 1:
            text = message.text.split(maxsplit=1)[1]
            LOGGER.info(f"Text taken from command args: {text[:100]}...")
        if not text:
            await processing_msg.edit_text(
                text="<b>⚠️ Please provide text or reply to a message❌</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.warning(f"No text provided for /text by user {message.from_user.id}")
            return
        response_text = f"<b>Inputed Text:</b>\n\n<code>{text}</code>"
        await processing_msg.edit_text(
            text=response_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_text_keyboard()
        )
        LOGGER.info(f"Text transformer menu sent successfully for /text")
    except Exception as e:
        LOGGER.error(f"Error in /text command: {str(e)}", exc_info=True)
        if processing_msg:
            try:
                await processing_msg.edit_text(
                    text="<b>❌ Sorry Bro, Invalid Text Provided!</b>",
                    parse_mode=ParseMode.HTML
                )
            except:
                pass
        await Smart_Notify(bot, "/text", e, message)

@dp.callback_query(lambda c: c.data and c.data.startswith("encoder:"))
async def handle_encoder_callback(callback: CallbackQuery, bot: Bot):
    method = callback.data.split(":", 1)[1]
    if method not in encoders:
        await callback.answer("Invalid method ❌", show_alert=True)
        return
    current_text = callback.message.html_text or callback.message.text or ""
    LOGGER.debug(f"Current message HTML text: {current_text[:300]}...")
    if "<b>Inputed Text:</b>" not in current_text:
        if f"<b>Encoded ({method.upper()}):</b>" in current_text:
            await callback.answer(f"Already Encoded Into {method.upper()} ❌", show_alert=True)
            return
    input_text = extract_input_text(current_text)
    if not input_text:
        LOGGER.warning(f"Failed to extract input text for encoder {method}. Full text: {current_text}")
        await callback.answer("Could not extract input text ❌", show_alert=True)
        return
    LOGGER.info(f"Extracted input text ({len(input_text)} chars) for encoding {method}")
    try:
        result = encoders[method](input_text)
        response_text = f"<b>Encoded ({method.upper()}):</b>\n\n<code>{result}</code>"
        await callback.message.edit_text(
            text=response_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_encoder_keyboard()
        )
        await callback.answer(f"Encoded using {method.upper()} ✅")
        LOGGER.info(f"Successfully encoded with {method}")
    except Exception as e:
        LOGGER.warning(f"Encoding failed for {method}: {str(e)}")
        response_text = f"<b>⚠️ Invalid for {method.upper()} encoding</b>\n\n<code>{input_text}</code>"
        await callback.message.edit_text(
            text=response_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_encoder_keyboard()
        )
        await callback.answer(f"This text cannot be encoded with {method.upper()} ❌", show_alert=True)

@dp.callback_query(lambda c: c.data and c.data.startswith("decoder:"))
async def handle_decoder_callback(callback: CallbackQuery, bot: Bot):
    method = callback.data.split(":", 1)[1]
    if method not in decoders:
        await callback.answer("Invalid method ❌", show_alert=True)
        return
    current_text = callback.message.html_text or callback.message.text or ""
    LOGGER.debug(f"Current message HTML text: {current_text[:300]}...")
    if "<b>Inputed Text:</b>" not in current_text:
        if f"<b>Decoded ({method.upper()}):</b>" in current_text:
            await callback.answer(f"Already Decoded Into {method.upper()} ❌", show_alert=True)
            return
    input_text = extract_input_text(current_text)
    if not input_text:
        LOGGER.warning(f"Failed to extract input text for decoder {method}. Full text: {current_text}")
        await callback.answer("Could not extract input text ❌", show_alert=True)
        return
    LOGGER.info(f"Extracted input text ({len(input_text)} chars) for decoding {method}")
    try:
        result = decoders[method](input_text)
        response_text = f"<b>Decoded ({method.upper()}):</b>\n\n<code>{result}</code>"
        await callback.message.edit_text(
            text=response_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_decoder_keyboard()
        )
        await callback.answer(f"Decoded using {method.upper()} ✅")
        LOGGER.info(f"Successfully decoded with {method}")
    except Exception as e:
        LOGGER.warning(f"Decoding failed for {method}: {str(e)}")
        response_text = f"<b>⚠️ Invalid for {method.upper()} decoding</b>\n\n<code>{input_text}</code>"
        await callback.message.edit_text(
            text=response_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_decoder_keyboard()
        )
        await callback.answer(f"This text cannot be decoded with {method.upper()} ❌", show_alert=True)

@dp.callback_query(lambda c: c.data and c.data.startswith("texttransform:"))
async def handle_text_callback(callback: CallbackQuery, bot: Bot):
    method = callback.data.split(":", 1)[1]
    if method not in text_transformers:
        await callback.answer("Invalid method ❌", show_alert=True)
        return
    current_text = callback.message.html_text or callback.message.text or ""
    LOGGER.debug(f"Current message HTML text: {current_text[:300]}...")
    if "<b>Inputed Text:</b>" not in current_text:
        if f"<b>Transformed ({method.upper()}):</b>" in current_text:
            await callback.answer(f"Already Transformed Into {method.upper()} ❌", show_alert=True)
            return
    input_text = extract_input_text(current_text)
    if not input_text:
        LOGGER.warning(f"Failed to extract input text for text transform {method}. Full text: {current_text}")
        await callback.answer("Could not extract input text ❌", show_alert=True)
        return
    LOGGER.info(f"Extracted input text ({len(input_text)} chars) for transform {method}")
    try:
        result = text_transformers[method](input_text)
        response_text = f"<b>Transformed ({method.upper()}):</b>\n\n<code>{result}</code>"
        await callback.message.edit_text(
            text=response_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_text_keyboard()
        )
        await callback.answer(f"Transformed using {method.upper()} ✅")
        LOGGER.info(f"Successfully transformed with {method}")
    except Exception as e:
        LOGGER.warning(f"Transformation failed for {method}: {str(e)}")
        response_text = f"<b>⚠️ Transformation error</b>\n\n<code>{input_text}</code>"
        await callback.message.edit_text(
            text=response_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_text_keyboard()
        )
        await callback.answer("Transformation failed ❌", show_alert=True)

@dp.callback_query(lambda c: c.data == "close_menu")
async def handle_close_callback(callback: CallbackQuery):
    try:
        LOGGER.info(f"Close menu requested by user {callback.from_user.id}")
        await callback.message.delete()
        await callback.answer("Closed ✅")
        LOGGER.info("Menu closed and message deleted")
    except Exception as e:
        LOGGER.error(f"Error closing menu: {str(e)}")
        await callback.answer("Could not delete message ❌", show_alert=True)