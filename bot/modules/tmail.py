import re
import time
import asyncio
import random
import string
import hashlib
import aiohttp
from bs4 import BeautifulSoup
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode, ChatType
from bot import dp
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.buttons import SmartButtons
from bot.helpers.defend import SmartDefender

user_data = {}
token_map = {}
user_tokens = {}
user_emails = {}
user_passwords = {}

MAX_MESSAGE_LENGTH = 4000

BASE_URL = "https://api.mail.tm"
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json"
}

def short_id_generator(email):
    unique_string = email + str(time.time())
    return hashlib.md5(unique_string.encode()).hexdigest()[:10]

def generate_random_username(length=8):
    return ''.join(random.choice(string.ascii_lowercase) for i in range(length))

def generate_random_password(length=12):
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for i in range(length))

async def get_domain():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/domains", headers=HEADERS) as response:
                data = await response.json()
                if isinstance(data, list) and data:
                    return data[0]['domain']
                elif 'hydra:member' in data and data['hydra:member']:
                    return data['hydra:member'][0]['domain']
    except Exception as e:
        LOGGER.error(f"Error fetching domain: {e}")
    return None

async def create_account(email, password):
    data = {
        "address": email,
        "password": password
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{BASE_URL}/accounts", headers=HEADERS, json=data) as response:
                if response.status in [200, 201]:
                    return await response.json()
                else:
                    LOGGER.error(f"Error Code: {response.status} Response: {await response.text()}")
                    return None
    except Exception as e:
        LOGGER.error(f"Error in create_account: {e}")
        return None

async def get_token(email, password):
    data = {
        "address": email,
        "password": password
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(f"{BASE_URL}/token", headers=HEADERS, json=data) as response:
                if response.status == 200:
                    return (await response.json()).get('token')
                else:
                    LOGGER.error(f"Token Error Code: {response.status} Token Response: {await response.text()}")
                    return None
    except Exception as e:
        LOGGER.error(f"Error in get_token: {e}")
        return None

def get_text_from_html(html_content_list):
    html_content = ''.join(html_content_list)
    soup = BeautifulSoup(html_content, 'html.parser')
    for a_tag in soup.find_all('a', href=True):
        url = a_tag['href']
        new_content = f"{a_tag.text} [{url}]"
        a_tag.string = new_content
    text_content = soup.get_text()
    cleaned_content = re.sub(r'\s+', ' ', text_content).strip()
    return cleaned_content

async def list_messages(token):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/messages", headers=headers) as response:
                data = await response.json()
                if isinstance(data, list):
                    return data
                elif 'hydra:member' in data:
                    return data['hydra:member']
                else:
                    return []
    except Exception as e:
        LOGGER.error(f"Error in list_messages: {e}")
        return []

async def get_account_by_token(token):
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/accounts", headers=headers) as response:
                data = await response.json()
                if isinstance(data, list) and data:
                    return data[0]
                elif 'hydra:member' in data and data['hydra:member']:
                    return data['hydra:member'][0]
                return None
    except Exception as e:
        LOGGER.error(f"Error in get_account_by_token: {e}")
        return None

@dp.message(Command(commands=["tmail"], prefix=BotCommands))
@new_task
@SmartDefender
async def generate_mail(message: Message, bot: Bot):
    chat_id = message.chat.id
    if message.chat.type != ChatType.PRIVATE:
        await send_message(
            chat_id=chat_id,
            text="<b>❌ Bro Tempmail Feature Only Works In Private</b>",
            parse_mode=ParseMode.HTML
        )
        return
    
    temp_message = await send_message(
        chat_id=chat_id,
        text="<b>Generating Temporary Mail...</b>",
        parse_mode=ParseMode.HTML
    )
    
    args = get_args(message)
    if len(args) == 1 and ':' in args[0]:
        username, password = args[0].split(':')
    else:
        username = generate_random_username()
        password = generate_random_password()
    
    domain = await get_domain()
    if not domain:
        await temp_message.edit_text(
            text="<b> Sorry Bro TempMail API Dead ❌</b>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        return
    
    email = f"{username}@{domain}"
    account = await create_account(email, password)
    if not account:
        await temp_message.edit_text(
            text="<b>❌ Username already taken. Choose another one.</b>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        return
    
    await asyncio.sleep(2)
    token = await get_token(email, password)
    if not token:
        await temp_message.edit_text(
            text="<b>❌ Failed to retrieve token</b>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        return
    
    short_id = short_id_generator(email)
    token_map[short_id] = token
    user_emails[short_id] = email
    user_passwords[short_id] = password
    
    output_message = (
        "<b>📧 SmartTools-Email Details 📧</b>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"<b>📧 Email:</b> <code>{email}</code>\n"
        f"<b>🔑 Password:</b> <code>{password}</code>\n"
        f"<b>🔒 Token:</b> <code>{token}</code>\n"
        "━━━━━━━━━━━━━━━━━━\n"
        "<b>Note: Keep the token to Access Mail</b>"
    )
    
    buttons = SmartButtons()
    buttons.button(text="Incoming Emails", callback_data=f"tmail_check_{short_id}")
    
    await temp_message.edit_text(
        text=output_message,
        parse_mode=ParseMode.HTML,
        reply_markup=buttons.build_menu(b_cols=1),
        disable_web_page_preview=True
    )

@dp.callback_query(lambda c: c.data.startswith('tmail_check_'))
async def check_mail(callback_query):
    chat_id = callback_query.message.chat.id
    short_id = callback_query.data.split('_')[2]
    token = token_map.get(short_id)
    email = user_emails.get(short_id)
    
    if not token or not email:
        await callback_query.answer("❌ Session expired, Please use /cmail with your token.", show_alert=True)
        return
    
    user_tokens[callback_query.from_user.id] = token
    user_data[callback_query.from_user.id] = {
        'email': email, 
        'password': user_passwords.get(short_id), 
        'short_id': short_id
    }
    
    messages = await list_messages(token)
    if not messages:
        await callback_query.answer("Sorry No Message Received", show_alert=True)
        return
    
    output = f"<b>📧 Email Address:</b> <code>{email}</code>\n"
    output += "<b>━━━━━━━━━━━━━━━━━━</b>\n"
    
    buttons = SmartButtons()
    for idx, msg in enumerate(messages[:5], 1):
        output += f"{idx}. From: <code>{msg['from']['address']}</code> - Subject: {msg['subject']}\n"
        buttons.button(text=f"{idx}", callback_data=f"tmail_read_{msg['id']}")
    
    buttons.button(text="Reveal Token", callback_data=f"tmail_reveal_token_{short_id}")
    buttons.button(text="Reveal Password", callback_data=f"tmail_reveal_pass_{short_id}")
    buttons.button(text="Refresh", callback_data=f"tmail_refresh_{short_id}")
    
    await callback_query.message.edit_text(
        text=output,
        parse_mode=ParseMode.HTML,
        reply_markup=buttons.build_menu(b_cols=1),
        disable_web_page_preview=True
    )

@dp.callback_query(lambda c: c.data.startswith('tmail_reveal_token_'))
async def reveal_token(callback_query):
    chat_id = callback_query.message.chat.id
    short_id = callback_query.data.split('_')[3]
    token = token_map.get(short_id)
    
    if not token:
        await callback_query.answer("❌ Token not found", show_alert=True)
        return
    
    buttons = SmartButtons()
    buttons.button(text="Close", callback_data="tmail_close_message")
    
    await send_message(
        chat_id=chat_id,
        text=f"<code>{token}</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=buttons.build_menu(b_cols=1)
    )

@dp.callback_query(lambda c: c.data.startswith('tmail_reveal_pass_'))
async def reveal_password(callback_query):
    chat_id = callback_query.message.chat.id
    short_id = callback_query.data.split('_')[3]
    password = user_passwords.get(short_id)
    
    if not password:
        await callback_query.answer("❌ Password not found", show_alert=True)
        return
    
    buttons = SmartButtons()
    buttons.button(text="Close", callback_data="tmail_close_message")
    
    await send_message(
        chat_id=chat_id,
        text=f"<code>{password}</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=buttons.build_menu(b_cols=1)
    )

@dp.callback_query(lambda c: c.data.startswith('tmail_refresh_'))
async def refresh_messages(callback_query):
    chat_id = callback_query.message.chat.id
    short_id = callback_query.data.split('_')[2]
    token = token_map.get(short_id)
    email = user_emails.get(short_id)
    
    if not token or not email:
        await callback_query.answer("❌ Session expired", show_alert=True)
        return
    
    current_message_text = callback_query.message.text
    current_message_count = len([line for line in current_message_text.split('\n') 
                                if line.strip() and line.strip()[0].isdigit()])
    
    messages = await list_messages(token)
    if not messages:
        await callback_query.answer("Sorry No New Message Received ❌", show_alert=True)
        return
    
    if len(messages) <= current_message_count:
        await callback_query.answer("Sorry No New Message Received ❌", show_alert=True)
        return
    
    output = f"<b>📧 Email Address:</b> <code>{email}</code>\n"
    output += "<b>━━━━━━━━━━━━━━━━━━</b>\n"
    
    buttons = SmartButtons()
    for idx, msg in enumerate(messages[:5], 1):
        output += f"{idx}. From: <code>{msg['from']['address']}</code> - Subject: {msg['subject']}\n"
        buttons.button(text=f"{idx}", callback_data=f"tmail_read_{msg['id']}")
    
    buttons.button(text="Reveal Token", callback_data=f"tmail_reveal_token_{short_id}")
    buttons.button(text="Reveal Password", callback_data=f"tmail_reveal_pass_{short_id}")
    buttons.button(text="Refresh", callback_data=f"tmail_refresh_{short_id}")
    
    await callback_query.message.edit_text(
        text=output,
        parse_mode=ParseMode.HTML,
        reply_markup=buttons.build_menu(b_cols=1),
        disable_web_page_preview=True
    )

@dp.callback_query(lambda c: c.data == "tmail_close_message")
async def close_message(callback_query):
    await delete_messages(callback_query.message.chat.id, callback_query.message.message_id)

@dp.callback_query(lambda c: c.data.startswith('tmail_read_'))
async def read_message(callback_query):
    chat_id = callback_query.message.chat.id
    message_id = callback_query.data.split('_')[2]
    token = user_tokens.get(callback_query.from_user.id)
    
    if not token:
        await send_message(
            chat_id=chat_id,
            text="<b>❌ Token not found. Please use /cmail with your token again</b>",
            parse_mode=ParseMode.HTML
        )
        return
    
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{BASE_URL}/messages/{message_id}", headers=headers) as response:
                if response.status == 200:
                    details = await response.json()
                    
                    if 'html' in details:
                        message_text = get_text_from_html(details['html'])
                    elif 'text' in details:
                        message_text = details['text']
                    else:
                        message_text = "Content not available."
                    
                    if len(message_text) > MAX_MESSAGE_LENGTH:
                        message_text = message_text[:MAX_MESSAGE_LENGTH - 100] + "... [message truncated]"
                    
                    output = (
                        f"<b>From:</b> <code>{details['from']['address']}</code>\n"
                        f"<b>Subject:</b> <code>{details['subject']}</code>\n"
                        "━━━━━━━━━━━━━━━━━━\n"
                        f"{message_text}"
                    )
                    
                    buttons = SmartButtons()
                    buttons.button(text="Close", callback_data="tmail_close_message")
                    
                    await send_message(
                        chat_id=chat_id,
                        text=output,
                        parse_mode=ParseMode.HTML,
                        reply_markup=buttons.build_menu(b_cols=1),
                        disable_web_page_preview=True
                    )
                else:
                    await send_message(
                        chat_id=chat_id,
                        text="<b>❌ Error retrieving message details</b>",
                        parse_mode=ParseMode.HTML
                    )
    except Exception as e:
        LOGGER.error(f"Error in read_message: {e}")
        await send_message(
            chat_id=chat_id,
            text="<b>❌ Error retrieving message details</b>",
            parse_mode=ParseMode.HTML
        )

@dp.message(Command(commands=["cmail"], prefix=BotCommands))
@new_task
@SmartDefender
async def manual_check_mail(message: Message, bot: Bot):
    chat_id = message.chat.id
    
    if message.chat.type != ChatType.PRIVATE:
        await send_message(
            chat_id=chat_id,
            text="<b>❌ Bro Tempmail Feature Only Works In Private</b>",
            parse_mode=ParseMode.HTML
        )
        return
    
    temp_message = await send_message(
        chat_id=chat_id,
        text="<code>Checking Temp-Mail Token...</code>",
        parse_mode=ParseMode.HTML
    )
    
    args = get_args(message)
    token = args[0] if args else ""
    
    if not token:
        await temp_message.edit_text(
            text="<b>❌ Please provide a token after the /cmail command.</b>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        return
    
    user_tokens[message.from_user.id] = token
    messages = await list_messages(token)
    
    if messages is None:
        await temp_message.edit_text(
            text="<b>Sorry Bro Invalid Token Provided</b>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        return
    
    await temp_message.edit_text(
        text="<b>Valid token detected ✅ Checking for sms...</b>",
        parse_mode=ParseMode.HTML
    )
    await asyncio.sleep(1)
    
    account = await get_account_by_token(token)
    if account:
        email = account.get('address', 'Unknown')
    else:
        email = "Unknown"
    
    if not messages:
        await temp_message.edit_text(
            text="<b>Sorry No Message Received</b>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        return
    
    short_id = short_id_generator(email)
    token_map[short_id] = token
    user_emails[short_id] = email
    user_data[message.from_user.id] = {'email': email, 'short_id': short_id}
    
    if not messages:
        await temp_message.edit_text(
            text="<b>Sorry No Message Received</b>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        return
    
    output = f"<b>📧 Email Address:</b> <code>{email}</code>\n"
    output += "<b>━━━━━━━━━━━━━━━━━━</b>\n"
    
    buttons = SmartButtons()
    for idx, msg in enumerate(messages[:5], 1):
        output += f"{idx}. From: <code>{msg['from']['address']}</code> - Subject: {msg['subject']}\n"
        buttons.button(text=f"{idx}", callback_data=f"tmail_read_{msg['id']}")
    
    buttons.button(text="Reveal Token", callback_data=f"tmail_reveal_token_{short_id}")
    buttons.button(text="Reveal Password", callback_data=f"tmail_reveal_pass_{short_id}")
    buttons.button(text="Refresh", callback_data=f"tmail_refresh_{short_id}")
    
    await temp_message.edit_text(
        text=output,
        parse_mode=ParseMode.HTML,
        reply_markup=buttons.build_menu(b_cols=1),
        disable_web_page_preview=True
    )
