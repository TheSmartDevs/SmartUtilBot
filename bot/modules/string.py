import aiohttp
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ParseMode, ChatType
from bot import dp
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.buttons import SmartButtons
from bot.helpers.defend import SmartDefender
from pyrogram import Client
from pyrogram.errors import ApiIdInvalid, PhoneNumberInvalid, PhoneCodeInvalid, PhoneCodeExpired, SessionPasswordNeeded, PasswordHashInvalid
from pyrogram.enums import ParseMode as SmartParseMode
from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import ApiIdInvalidError, PhoneNumberInvalidError, PhoneCodeInvalidError, PhoneCodeExpiredError, SessionPasswordNeededError, PasswordHashInvalidError
from asyncio.exceptions import TimeoutError
import asyncio
import re

logger = LOGGER
TIMEOUT_OTP = 600
TIMEOUT_2FA = 300
session_data = {}

@dp.message(Command(commands=["pyro", "tele"], prefix=BotCommands))
@new_task
@SmartDefender
async def session_setup(message: Message, bot: Bot):
    user_id = message.from_user.id
    chat_id = message.chat.id
    if message.chat.type != ChatType.PRIVATE:
        await send_message(
            chat_id=chat_id,
            text="<b>❌ String Session Generator Only Works In Private Chats</b>",
            parse_mode=ParseMode.HTML
        )
        return
    await cleanup_session(chat_id)
    text = message.text
    if isinstance(BotCommands, str):
        prefix_length = len(BotCommands)
    else:
        for p in BotCommands:
            if text.startswith(p):
                prefix_length = len(p)
                break
        else:
            prefix_length = len(BotCommands[0])
    command = text[prefix_length:].lower()
    platform = "PyroGram" if command == "pyro" else "Telethon"
    await handle_start(bot, message, platform)

@dp.callback_query(lambda c: c.data.startswith(("start_session", "restart_session", "close_session")))
@new_task
@SmartDefender
async def callback_query_handler(callback_query: CallbackQuery, bot: Bot):
    user_id = callback_query.from_user.id
    chat_id = callback_query.message.chat.id
    if chat_id not in session_data:
        await callback_query.answer("Session expired. Please start again with /pyro or /tele", show_alert=True)
        return
    await handle_callback_query(bot, callback_query)

@dp.message(lambda message: message.chat.type == ChatType.PRIVATE and not message.from_user.is_bot and message.text and not message.text.startswith(tuple(BotCommands)) and message.chat.id in session_data and session_data[message.chat.id].get("stage") and (
    (session_data[message.chat.id].get("stage") == "api_id" and re.match(r'^\d+$', message.text.strip())) or
    (session_data[message.chat.id].get("stage") == "api_hash" and re.match(r'^[a-fA-F0-9]{32}$', message.text.strip())) or
    (session_data[message.chat.id].get("stage") == "phone_number" and re.match(r'^\+\d{10,15}$', message.text.strip())) or
    (session_data[message.chat.id].get("stage") == "otp" and re.match(r'^[\d\s-]{4,12}$', message.text.strip())) or
    (session_data[message.chat.id].get("stage") == "2fa" and len(message.text.strip()) <= 20)
))
@new_task
@SmartDefender
async def text_handler(message: Message, bot: Bot):
    user_id = message.from_user.id
    chat_id = message.chat.id
    session = session_data[chat_id]
    if not session.get("stage"):
        return
    if user_id != session.get("user_id"):
        return
    await handle_text(bot, message)

async def handle_start(bot: Bot, message: Message, platform: str):
    session_type = "Telethon" if platform == "Telethon" else "Pyrogram"
    session_data[message.chat.id] = {"type": session_type, "user_id": message.from_user.id}
    buttons = SmartButtons()
    buttons.button(text="Start", callback_data=f"start_session_{session_type.lower()}")
    buttons.button(text="Close", callback_data="close_session")
    await send_message(
        chat_id=message.chat.id,
        text=(
            f"<b>Welcome To Secure {session_type} Session Generator !</b>\n"
            "<b>━━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
            "This is a totally safe session string generator. We don't save any info that you will provide, so this is completely safe.\n\n"
            "<b>📵 Note: </b> Don't send OTP directly. Otherwise, you may not be able to log in.\n\n"
            "<b>⚠️ Warn: </b> Using the session for policy-violating activities may result in your Telegram account getting banned or deleted.\n\n"
            "❌ We are not responsible for any issues that may occur due to misuse."
        ),
        parse_mode=ParseMode.HTML,
        reply_markup=buttons.build_menu(b_cols=2)
    )

async def handle_callback_query(bot: Bot, callback_query: CallbackQuery):
    data = callback_query.data
    chat_id = callback_query.message.chat.id
    if chat_id not in session_data:
        await callback_query.answer("Session expired. Please start again with /pyro or /tele", show_alert=True)
        return
    session = session_data[chat_id]
    if callback_query.from_user.id != session.get("user_id"):
        await callback_query.answer("This session belongs to another user!", show_alert=True)
        return
    if data == "close_session":
        platform = session.get("type", "").lower()
        if platform == "pyrogram":
            await callback_query.message.edit_text(
                text="<b>❌Cancelled. You can start by sending /pyro</b>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        elif platform == "telethon":
            await callback_query.message.edit_text(
                text="<b>❌Cancelled. You can start by sending /tele</b>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        await cleanup_session(chat_id)
        return
    if data.startswith("start_session_"):
        session_type = data.split('_')[2]
        buttons = SmartButtons()
        buttons.button(text="Restart", callback_data=f"restart_session_{session_type}")
        buttons.button(text="Close", callback_data="close_session")
        await callback_query.message.edit_text(
            text="<b>Send Your API ID</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=buttons.build_menu(b_cols=2)
        )
        session["stage"] = "api_id"
    if data.startswith("restart_session_"):
        session_type = data.split('_')[2]
        await cleanup_session(chat_id)
        await handle_start(bot, callback_query.message, platform=session_type.capitalize())

async def handle_text(bot: Bot, message: Message):
    chat_id = message.chat.id
    session = session_data[chat_id]
    stage = session.get("stage")
    if stage == "api_id":
        try:
            api_id = int(message.text)
            session["api_id"] = api_id
            buttons = SmartButtons()
            buttons.button(text="Restart", callback_data=f"restart_session_{session['type'].lower()}")
            buttons.button(text="Close", callback_data="close_session")
            await send_message(
                chat_id=chat_id,
                text="<b>Send Your API Hash</b>",
                parse_mode=ParseMode.HTML,
                reply_markup=buttons.build_menu(b_cols=2)
            )
            session["stage"] = "api_hash"
        except ValueError:
            await send_message(
                chat_id=chat_id,
                text="<b>❌Invalid API ID. Please enter a valid integer.</b>",
                parse_mode=ParseMode.HTML
            )
            logger.error(f"Invalid API ID provided by user {message.from_user.id}")
    elif stage == "api_hash":
        session["api_hash"] = message.text
        buttons = SmartButtons()
        buttons.button(text="Restart", callback_data=f"restart_session_{session['type'].lower()}")
        buttons.button(text="Close", callback_data="close_session")
        await send_message(
            chat_id=chat_id,
            text="<b>Send Your Phone Number\n[Example: +880xxxxxxxxxx]</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=buttons.build_menu(b_cols=2)
        )
        session["stage"] = "phone_number"
    elif stage == "phone_number":
        session["phone_number"] = message.text
        otp_message = await send_message(
            chat_id=chat_id,
            text="<b>Sending OTP Check PM.....</b>",
            parse_mode=ParseMode.HTML
        )
        await send_otp(bot, message, otp_message)
    elif stage == "otp":
        otp = ''.join([char for char in message.text if char.isdigit()])
        session["otp"] = otp
        otp_message = await send_message(
            chat_id=chat_id,
            text="<b>Checking & Processing Your OTP</b>",
            parse_mode=ParseMode.HTML
        )
        await validate_otp(bot, message, otp_message)
    elif stage == "2fa":
        session["password"] = message.text
        await validate_2fa(bot, message)

async def cleanup_session(chat_id):
    if chat_id in session_data:
        session = session_data[chat_id]
        client_obj = session.get("client_obj")
        if client_obj:
            try:
                await client_obj.disconnect()
                if session["type"] == "Pyrogram":
                    session_file = ":memory:.session"
                    clean_download(session_file)
                    logger.info(f"Deleted temporary session file {session_file} for user {chat_id}")
            except Exception as e:
                logger.error(f"Error during session cleanup for user {chat_id}: {str(e)}")
        del session_data[chat_id]
        logger.info(f"Session data cleared for user {chat_id}")

async def send_otp(bot: Bot, message: Message, otp_message: Message):
    session = session_data[message.chat.id]
    api_id = session["api_id"]
    api_hash = session["api_hash"]
    phone_number = session["phone_number"]
    telethon = session["type"] == "Telethon"
    if telethon:
        client_obj = TelegramClient(StringSession(), api_id, api_hash)
    else:
        client_obj = Client(":memory:", api_id, api_hash)
    await client_obj.connect()
    try:
        if telethon:
            code = await client_obj.send_code_request(phone_number)
        else:
            code = await client_obj.send_code(phone_number)
        session["client_obj"] = client_obj
        session["code"] = code
        session["stage"] = "otp"
        asyncio.create_task(handle_otp_timeout(bot, message))
        buttons = SmartButtons()
        buttons.button(text="Restart", callback_data=f"restart_session_{session['type'].lower()}")
        buttons.button(text="Close", callback_data="close_session")
        await send_message(
            chat_id=message.chat.id,
            text="<b>✅Send The OTP as text. Please send a text message embedding the OTP like: 'AB5 CD0 EF3 GH7 IJ6'</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=buttons.build_menu(b_cols=2)
        )
        await delete_messages(message.chat.id, otp_message.message_id)
    except (ApiIdInvalid, ApiIdInvalidError):
        buttons = SmartButtons()
        buttons.button(text="Restart", callback_data=f"restart_session_{session['type'].lower()}")
        buttons.button(text="Close", callback_data="close_session")
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ <code>API_ID</code> and <code>API_HASH</code> combination is invalid</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=buttons.build_menu(b_cols=2)
        )
        await delete_messages(message.chat.id, otp_message.message_id)
        logger.error(f"Invalid API_ID/API_HASH for user {message.from_user.id}")
        await cleanup_session(message.chat.id)
        return
    except (PhoneNumberInvalid, PhoneNumberInvalidError):
        buttons = SmartButtons()
        buttons.button(text="Restart", callback_data=f"restart_session_{session['type'].lower()}")
        buttons.button(text="Close", callback_data="close_session")
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌<code>PHONE_NUMBER</code> is invalid.</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=buttons.build_menu(b_cols=2)
        )
        await delete_messages(message.chat.id, otp_message.message_id)
        logger.error(f"Invalid phone number for user {message.from_user.id}")
        await cleanup_session(message.chat.id)
        return

async def handle_otp_timeout(bot: Bot, message: Message):
    await asyncio.sleep(TIMEOUT_OTP)
    if message.chat.id in session_data and session_data[message.chat.id].get("stage") == "otp":
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Bro Your OTP Has Expired</b>",
            parse_mode=ParseMode.HTML
        )
        await cleanup_session(message.chat.id)
        logger.info(f"OTP timed out for user {message.from_user.id}")

async def validate_otp(bot: Bot, message: Message, otp_message: Message):
    session = session_data[message.chat.id]
    client_obj = session["client_obj"]
    phone_number = session["phone_number"]
    otp = session["otp"]
    code = session["code"]
    telethon = session["type"] == "Telethon"
    try:
        if telethon:
            await client_obj.sign_in(phone_number, otp)
        else:
            await client_obj.sign_in(phone_number, code.phone_code_hash, otp)
        await generate_session(bot, message)
        await delete_messages(message.chat.id, otp_message.message_id)
    except (PhoneCodeInvalid, PhoneCodeInvalidError):
        buttons = SmartButtons()
        buttons.button(text="Restart", callback_data=f"restart_session_{session['type'].lower()}")
        buttons.button(text="Close", callback_data="close_session")
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌Bro Your OTP Is Wrong</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=buttons.build_menu(b_cols=2)
        )
        await delete_messages(message.chat.id, otp_message.message_id)
        logger.error(f"Invalid OTP provided by user {message.from_user.id}")
        await cleanup_session(message.chat.id)
        return
    except (PhoneCodeExpired, PhoneCodeExpiredError):
        buttons = SmartButtons()
        buttons.button(text="Restart", callback_data=f"restart_session_{session['type'].lower()}")
        buttons.button(text="Close", callback_data="close_session")
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌Bro OTP Has expired</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=buttons.build_menu(b_cols=2)
        )
        await delete_messages(message.chat.id, otp_message.message_id)
        logger.error(f"Expired OTP for user {message.from_user.id}")
        await cleanup_session(message.chat.id)
        return
    except (SessionPasswordNeeded, SessionPasswordNeededError):
        session["stage"] = "2fa"
        asyncio.create_task(handle_2fa_timeout(bot, message))
        buttons = SmartButtons()
        buttons.button(text="Restart", callback_data=f"restart_session_{session['type'].lower()}")
        buttons.button(text="Close", callback_data="close_session")
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ 2FA Is Required To Login. Please Enter 2FA</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=buttons.build_menu(b_cols=2)
        )
        await delete_messages(message.chat.id, otp_message.message_id)
        logger.info(f"2FA required for user {message.from_user.id}")

async def handle_2fa_timeout(bot: Bot, message: Message):
    await asyncio.sleep(TIMEOUT_2FA)
    if message.chat.id in session_data and session_data[message.chat.id].get("stage") == "2fa":
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Bro Your 2FA Input Has Expired</b>",
            parse_mode=ParseMode.HTML
        )
        await cleanup_session(message.chat.id)
        logger.info(f"2FA timed out for user {message.from_user.id}")

async def validate_2fa(bot: Bot, message: Message):
    session = session_data[message.chat.id]
    client_obj = session["client_obj"]
    password = session["password"]
    telethon = session["type"] == "Telethon"
    try:
        if telethon:
            await client_obj.sign_in(password=password)
        else:
            await client_obj.check_password(password=password)
        await generate_session(bot, message)
    except (PasswordHashInvalid, PasswordHashInvalidError):
        buttons = SmartButtons()
        buttons.button(text="Restart", callback_data=f"restart_session_{session['type'].lower()}")
        buttons.button(text="Close", callback_data="close_session")
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌Invalid Password Provided</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=buttons.build_menu(b_cols=2)
        )
        logger.error(f"Invalid 2FA password provided by user {message.from_user.id}")
        await cleanup_session(message.chat.id)
        return

async def generate_session(bot: Bot, message: Message):
    session = session_data[message.chat.id]
    client_obj = session["client_obj"]
    telethon = session["type"] == "Telethon"
    if telethon:
        string_session = client_obj.session.save()
    else:
        string_session = await client_obj.export_session_string()
    text = (
        f"<b>{session['type']} Session String From Smart Tool</b>\n"
        "<b>━━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"<code>{string_session}</code>\n"
        "<b>━━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        "<b>⚠️ Warn: </b> Using the session for policy-violating activities may result in your Telegram account getting banned or deleted."
    )
    try:
        if telethon:
            await client_obj.send_message("me", text, parse_mode="html")
        else:
            await client_obj.send_message("me", text, parse_mode=SmartParseMode.HTML)
    except KeyError:
        logger.error(f"Failed to send session string to saved messages for user {message.from_user.id}")
        pass
    await cleanup_session(message.chat.id)
    await send_message(
        chat_id=message.chat.id,
        text="<b>This string has been saved ✅ in your Saved Messages</b>",
        parse_mode=ParseMode.HTML
    )
    logger.info(f"Session string generated successfully for user {message.from_user.id}")