#Copyright @ISmartDevs
#Channel t.me/TheSmartDev
#Note This Script Based On https://github.com/abirxdhack/Mail-Scrapper
import logging
import re
import os
import aiofiles
import asyncio
from urllib.parse import urlparse
from pyrogram import Client, filters
from user import user 
from pyrogram.enums import ParseMode
from pyrogram.errors import (
    UserAlreadyParticipant,
    InviteHashExpired,
    InviteHashInvalid,
    PeerIdInvalid,
    InviteRequestSent
)
from config import COMMAND_PREFIX, MAIL_SCR_LIMIT, SUDO_MAILSCR_LIMIT, OWNER_IDS

# Set up logging For Proper Error Capture 
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def filter_messages(message):
    if message is None:
        return []

    pattern = r'(\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b:\S+)'
    matches = re.findall(pattern, message)

    return matches

async def collect_channel_data(channel_identifier, amount):
    messages = []
    async for message in user.search_messages(channel_identifier, limit=amount):
        matches = filter_messages(message.text)
        if matches:
            messages.extend(matches)

        if len(messages) >= amount:
            break

    unique_messages = list(set(messages))
    duplicates_removed = len(messages) - len(unique_messages)

    if not unique_messages:
        return [], 0, "<b>❌ No Email and Password Combinations were found</b>"

    return unique_messages[:amount], duplicates_removed, None

async def join_private_chat(client, invite_link):
    try:
        await client.join_chat(invite_link)
        logger.info(f"Joined chat via invite link: {invite_link}")
        return True
    except UserAlreadyParticipant:
        logger.info(f"Already a participant in the chat: {invite_link}")
        return True
    except InviteRequestSent:
        logger.info(f"Join request sent to the chat: {invite_link}")
        return False
    except (InviteHashExpired, InviteHashInvalid) as e:
        logger.error(f"Failed to join chat {invite_link}: {e}")
        return False

async def send_join_request(client, invite_link, message):
    try:
        await client.join_chat(invite_link)
        logger.info(f"Sent join request to chat: {invite_link}")
        await message.edit_text("<b>Hey Bro I Have Sent Join Request✅</b>", parse_mode=ParseMode.HTML)
        return True
    except PeerIdInvalid as e:
        logger.error(f"Failed to send join request to chat {invite_link}: {e}")
        await message.edit_text("<b>Hey Bro Incorrect Invite Link ❌</b>", parse_mode=ParseMode.HTML)
        return False
    except InviteRequestSent:
        logger.info(f"Join request sent to the chat: {invite_link}")
        await message.edit_text("<b>Hey Bro I Have Sent Join Request✅</b>", parse_mode=ParseMode.HTML)
        return False

def get_user_info(message):
    if message.from_user:
        user_full_name = f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
        user_info = f"[{user_full_name}](tg://user?id={message.from_user.id})"
    else:
        group_name = message.chat.title or "this group"
        group_url = f"https://t.me/{message.chat.username}" if message.chat.username else "this group"
        user_info = f"[{group_name}]({group_url})"
    return user_info

def setup_mailscr_handler(app):
    @app.on_message(filters.command(["scrmail", "mailscr"], prefixes=COMMAND_PREFIX) & (filters.group | filters.private))
    async def collect_handler(client, message):
        args = message.text.split()
        if len(args) < 3:
            await client.send_message(message.chat.id, "<b>❌ Please provide a channel with amount</b>", parse_mode=ParseMode.HTML)
            return

        # Extract channel identifier (username, invite link, or chat ID)
        channel_identifier = args[1]
        try:
            amount = int(args[2])
        except ValueError:
            await client.send_message(message.chat.id, "<b>❌ Amount must be a number</b>", parse_mode=ParseMode.HTML)
            return

        # Check if user is a sudo user
        is_sudo = message.from_user and message.from_user.id in OWNER_IDS
        max_limit = SUDO_MAILSCR_LIMIT if is_sudo else MAIL_SCR_LIMIT

        # Enforce the amount limit
        if amount > max_limit:
            await client.send_message(
                message.chat.id,
                f"<b>❌ Amount exceeds limit. Maximum allowed is {max_limit}.</b>",
                parse_mode=ParseMode.HTML
            )
            return

        chat = None
        channel_name = ""

        progress_message = await client.send_message(message.chat.id, "<b>Checking Username...✨</b>", parse_mode=ParseMode.HTML)

        # Handle private channel chat ID (numeric)
        if channel_identifier.lstrip("-").isdigit():
            # Treat it as a chat ID
            chat_id = int(channel_identifier)
            try:
                # Fetch the chat details
                chat = await user.get_chat(chat_id)
                channel_name = chat.title
                logger.info(f"Scraping from private channel: {channel_name} (ID: {chat_id})")
            except Exception as e:
                await progress_message.edit_text("<b>Hey Bro Incorrect ChatId ❌</b>", parse_mode=ParseMode.HTML)
                logger.error(f"Failed to fetch private channel: {e}")
                return
        else:
            if channel_identifier.startswith("https://t.me/+"):
                invite_link = channel_identifier
                joined = await join_private_chat(user, invite_link)
                if not joined:
                    request_sent = await send_join_request(user, invite_link, progress_message)
                    if not request_sent:
                        return
                else:
                    chat = await user.get_chat(invite_link)
                    channel_name = chat.title
                    logger.info(f"Joined private channel via link: {channel_name}")
                    channel_identifier = chat.id  # Use chat ID for further operations
            else:
                # Handle public channels
                channel_username = channel_identifier
                try:
                    chat = await user.get_chat(channel_username)
                    channel_name = chat.title
                except Exception as e:
                    await progress_message.edit_text(f"<b>Hey Bro Incorrect Username ❌</b>", parse_mode=ParseMode.HTML)
                    logger.error(f"Failed to fetch channel: {e}")
                    return

        await progress_message.edit_text("<b>Scraping In Progress</b>", parse_mode=ParseMode.HTML)

        messages, duplicates_removed, error_msg = await collect_channel_data(channel_identifier, amount)

        if error_msg:
            await progress_message.edit_text(error_msg, parse_mode=ParseMode.HTML)
            return

        if not messages:
            await progress_message.edit_text("<b>Sorry Bro ❌ No Mail Pass Found</b>", parse_mode=ParseMode.HTML)
            return

        file_path = f'{channel_identifier}_combos.txt'
        async with aiofiles.open(file_path, 'w', encoding='utf-8') as file:
            for combo in messages:
                try:
                    await file.write(f"{combo}\n")
                except UnicodeEncodeError:
                    continue

        output_message = (f"<b>Mail Scraped Successful ✅</b>\n"
                          f"<b>━━━━━━━━━━━━━━━━</b>\n"
                          f"<b>Source:</b> <code>{channel_name} 🌐</code>\n"
                          f"<b>Amount:</b> <code>{len(messages)} 📝</code>\n"
                          f"<b>Duplicates Removed:</b> <code>{duplicates_removed} 🗑️</code>\n"
                          f"<b>━━━━━━━━━━━━━━━━</b>\n"
                          f"<b>SCRAPED BY <a href='https://t.me/ItsSmartToolBot'>Smart Tool ⚙️</a></b>")
        await client.send_document(message.chat.id, file_path, caption=output_message, parse_mode=ParseMode.HTML)

        os.remove(file_path)
        await progress_message.delete()