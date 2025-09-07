# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
#  Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
import re
import os
import asyncio
import aiofiles
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from pyrogram.errors import (
    UserAlreadyParticipant,
    InviteHashExpired,
    InviteHashInvalid,
    PeerIdInvalid,
    InviteRequestSent
)
from pyrogram.enums import ParseMode as SmartParseMode
from urllib.parse import urlparse
from bot import dp, SmartUserBot, SmartAIO
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.defend import SmartDefender
from config import (
    SUDO_MAILSCR_LIMIT,
    OWNER_ID,
    MAIL_SCR_LIMIT
)

async def filter_messages(message):
    LOGGER.info("Filtering message for email and password combinations")
    if message is None or (not message.text and not message.caption):
        LOGGER.warning("Message is None or has no text/caption, returning empty list")
        return []
    text = message.text or message.caption
    pattern = r'(\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b:\S+)'
    matches = re.findall(pattern, text)
    LOGGER.info(f"Found {len(matches)} matches in message")
    return matches

async def collect_channel_data(client, channel_identifier, amount):
    LOGGER.info(f"Collecting data from channel: {channel_identifier} with limit: {amount}")
    messages = []
    message_count = 0
    async for message in client.search_messages(channel_identifier):
        message_count += 1
        matches = await filter_messages(message)
        if matches:
            messages.extend(matches)
            LOGGER.info(f"Collected {len(matches)} email-password combos from message {message_count}")
        if message_count >= amount:
            LOGGER.info(f"Reached message scan limit of {amount}, stopping collection")
            break
    unique_messages = list(set(messages))
    duplicates_removed = len(messages) - len(unique_messages)
    LOGGER.info(f"Scanned {message_count} messages, Total combos: {len(messages)}, Unique combos: {len(unique_messages)}, Duplicates removed: {duplicates_removed}")
    if not unique_messages:
        LOGGER.warning("No email and password combinations found")
        return [], 0, "<b>❌ No Email and Password Combinations were found</b>"
    return unique_messages[:amount], duplicates_removed, None

async def join_private_chat(client, invite_link):
    LOGGER.info(f"Attempting to join private chat: {invite_link}")
    try:
        await client.join_chat(invite_link)
        LOGGER.info(f"Successfully joined chat via invite link: {invite_link}")
        return True
    except UserAlreadyParticipant:
        LOGGER.info(f"Already a participant in the chat: {invite_link}")
        return True
    except InviteRequestSent:
        LOGGER.info(f"Join request sent to the chat: {invite_link}")
        return False
    except (InviteHashExpired, InviteHashInvalid) as e:
        LOGGER.error(f"Failed to join chat {invite_link}: {e}")
        return False

async def send_join_request(client, invite_link, message):
    LOGGER.info(f"Sending join request to chat: {invite_link}")
    try:
        await client.join_chat(invite_link)
        LOGGER.info(f"Join request sent successfully to chat: {invite_link}")
        return True
    except PeerIdInvalid as e:
        LOGGER.error(f"Failed to send join request to chat {invite_link}: {e}")
        await message.edit_text("<b>Hey Bro Incorrect Invite Link ❌</b>", parse_mode=SmartParseMode.HTML)
        return False
    except InviteRequestSent:
        LOGGER.info(f"Join request sent to the chat: {invite_link}")
        await message.edit_text("<b>Hey Bro I Have Sent Join Request✅</b>", parse_mode=SmartParseMode.HTML)
        return False

async def get_user_link(message):
    LOGGER.info("Retrieving user information")
    if message.from_user and message.chat.type == "private":
        user_first_name = message.from_user.first_name
        user_last_name = message.from_user.last_name or ""
        user_full_name = f"{user_first_name} {user_last_name}".strip()
        user_info = f"tg://user?id={message.from_user.id}"
        LOGGER.info(f"User info: {user_full_name}, {user_info}")
        return f'<a href="{user_info}">{user_full_name}</a>'
    else:
        user_full_name = message.chat.title or "this group"
        user_info = f"https://t.me/{message.chat.username}" if message.chat.username else "this group"
        LOGGER.info(f"Group info: {user_full_name}, {user_info}")
        return f'<a href="{user_info}">{user_full_name}</a>'

@dp.message(Command(commands=["scrmail", "mailscr"], prefix=BotCommands))
@new_task
@SmartDefender
async def mailscr_command(message: Message, bot: Bot):
    user_id = message.from_user.id if message.from_user else None
    args = get_args(message)
    if len(args) < 2:
        LOGGER.warning("Insufficient arguments provided")
        await send_message(message.chat.id, "<b>❌ Please provide a channel with amount</b>", parse_mode=SmartParseMode.HTML)
        return
    channel_identifier = args[0]
    try:
        amount = int(args[1])
    except ValueError:
        LOGGER.warning("Invalid amount provided")
        await send_message(message.chat.id, "<b>❌ Amount must be a number</b>", parse_mode=SmartParseMode.HTML)
        return
    limit = SUDO_MAILSCR_LIMIT if user_id and user_id in (OWNER_ID if isinstance(OWNER_ID, (list, tuple)) else [OWNER_ID]) else MAIL_SCR_LIMIT
    LOGGER.info(f"User ID: {user_id}, Applying limit: {limit}")
    if amount > limit:
        LOGGER.warning(f"Requested amount {amount} exceeds limit {limit} for user {user_id}")
        await send_message(message.chat.id, f"<b>❌ Amount exceeds limit of {limit}</b>", parse_mode=SmartParseMode.HTML)
        return
    chat = None
    channel_name = ""
    channel_username = ""
    temporary_msg = await send_message(message.chat.id, "<b>Checking Username...</b>", parse_mode=SmartParseMode.HTML)
    LOGGER.info(f"Sent progress message: Checking Username...")
    if channel_identifier.lstrip("-").isdigit():
        chat_id = int(channel_identifier)
        LOGGER.info(f"Processing chat ID: {chat_id}")
        try:
            chat = await SmartUserBot.get_chat(chat_id)
            channel_name = chat.title
            LOGGER.info(f"Successfully fetched private channel: {channel_name} (ID: {chat_id})")
        except Exception as e:
            LOGGER.error(f"Failed to fetch private channel {chat_id}: {e}")
            await temporary_msg.edit_text("<b>Hey Bro Incorrect ChatId ❌</b>", parse_mode=SmartParseMode.HTML)
            return
    else:
        if channel_identifier.startswith("https://t.me/+"):
            invite_link = channel_identifier
            LOGGER.info(f"Detected private channel invite link: {invite_link}")
            joined = await join_private_chat(SmartUserBot, invite_link)
            if not joined:
                LOGGER.info(f"Join not completed, sending join request for: {invite_link}")
                request_sent = await send_join_request(SmartUserBot, invite_link, temporary_msg)
                if not request_sent:
                    return
            else:
                chat = await SmartUserBot.get_chat(invite_link)
                channel_name = chat.title
                LOGGER.info(f"Joined private channel: {channel_name}")
                channel_identifier = chat.id
        elif channel_identifier.startswith(("https://t.me/", "t.me/")):
            channel_username = channel_identifier.split("t.me/")[-1]
            channel_username = f"@{channel_username}" if not channel_username.startswith("@") else channel_username
            LOGGER.info(f"Processing public channel username: {channel_username}")
        else:
            channel_username = channel_identifier
            channel_username = f"@{channel_username}" if not channel_username.startswith("@") else channel_username
            LOGGER.info(f"Processing public channel username: {channel_username}")
        if not chat:
            try:
                chat = await SmartUserBot.get_chat(channel_username)
                channel_name = chat.title
                LOGGER.info(f"Successfully fetched public channel: {channel_name}")
            except Exception as e:
                LOGGER.error(f"Failed to fetch public channel {channel_username}: {e}")
                await temporary_msg.edit_text("<b>Hey Bro Incorrect Username ❌</b>", parse_mode=SmartParseMode.HTML)
                return
    await temporary_msg.edit_text("<b>Scraping In Progress</b>", parse_mode=SmartParseMode.HTML)
    LOGGER.info("Updated progress message: Scraping In Progress")
    messages, duplicates_removed, error_msg = await collect_channel_data(SmartUserBot, chat.id, amount)
    if error_msg:
        LOGGER.error(f"Error during data collection: {error_msg}")
        await temporary_msg.edit_text(error_msg, parse_mode=SmartParseMode.HTML)
        return
    if not messages:
        LOGGER.warning("No email and password combinations found")
        await temporary_msg.edit_text("<b>❌ No Email and Password Combinations were found</b>", parse_mode=SmartParseMode.HTML)
        return
    file_name = f"x{len(messages)}_mail_results.txt"
    LOGGER.info(f"Writing {len(messages)} combos to file: {file_name}")
    async with aiofiles.open(file_name, 'w', encoding='utf-8') as file:
        for combo in messages:
            try:
                await file.write(f"{combo}\n")
            except UnicodeEncodeError:
                LOGGER.warning(f"Skipped combo due to UnicodeEncodeError: {combo}")
                continue
    user_link = await get_user_link(message)
    output_message = (
        f"<b>Mail Scraped Successful ✅</b>\n"
        f"<b>━━━━━━━━━━━━━━━━</b>\n"
        f"<b>Source:</b> <code>{channel_name} 🌐</code>\n"
        f"<b>Amount:</b> <code>{len(messages)} 📝</code>\n"
        f"<b>Duplicates Removed:</b> <code>{duplicates_removed} 🗑️</code>\n"
        f"<b>━━━━━━━━━━━━━━━━</b>\n"
        f"<b>Scrapped By:</b> {user_link}"
    )
    try:
        LOGGER.info(f"Attempting to send document {file_name} to chat {message.chat.id}")
        await SmartAIO.send_document(
            chat_id=message.chat.id,
            document=FSInputFile(file_name),
            caption=output_message,
            parse_mode=SmartParseMode.HTML
        )
        LOGGER.info(f"Successfully sent document {file_name} to chat {message.chat.id}")
        await delete_messages(message.chat.id, [temporary_msg.message_id])
    except Exception as e:
        LOGGER.error(f"Failed to send document {file_name}: {e}")
        await temporary_msg.edit_text("<b>Sorry Bro ❌ Failed to Send Results</b>")
        await Smart_Notify(bot, f"{BotCommands}scrmail", e, message)
    finally:
        if os.path.exists(file_name):
            LOGGER.info(f"Removing temporary file {file_name}")
            clean_download(file_name)