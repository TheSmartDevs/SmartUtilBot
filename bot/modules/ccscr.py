# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
#  Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
import re
import os
import time
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
from bot.helpers.pgbar import progress_bar
from bot.helpers.defend import SmartDefender
from config import (
    SUDO_CCSCR_LIMIT,
    OWNER_ID,
    CC_SCRAPPER_LIMIT,
    MULTI_CCSCR_LIMIT
)

async def scrape_messages(client, channel_identifier, limit, start_number=None, bank_name=None):
    messages = []
    count = 0
    pattern = r'\d{16}\D*\d{2}\D*\d{2,4}\D*\d{3,4}'
    bin_pattern = re.compile(r'^\d{6}') if start_number else None
    LOGGER.info(f"Starting to scrape messages from {channel_identifier} with limit {limit}")
    async for message in client.search_messages(channel_identifier):
        if count >= limit:
            break
        text = message.text or message.caption
        if text:
            if bank_name and bank_name.lower() not in text.lower():
                continue
            matched_messages = re.findall(pattern, text)
            if matched_messages:
                formatted_messages = []
                for matched_message in matched_messages:
                    extracted_values = re.findall(r'\d+', matched_message)
                    if len(extracted_values) == 4:
                        card_number, mo, year, cvv = extracted_values
                        year = year[-2:]
                        if start_number:
                            if card_number.startswith(start_number[:6]):
                                formatted_messages.append(f"{card_number}|{mo}|{year}|{cvv}")
                        else:
                            formatted_messages.append(f"{card_number}|{mo}|{year}|{cvv}")
                messages.extend(formatted_messages)
                count += len(formatted_messages)
    LOGGER.info(f"Scraped {len(messages)} messages from {channel_identifier}")
    return messages[:limit]

def remove_duplicates(messages):
    unique_messages = list(set(messages))
    duplicates_removed = len(messages) - len(unique_messages)
    LOGGER.info(f"Removed {duplicates_removed} duplicates")
    return unique_messages, duplicates_removed

async def send_results(bot, message, unique_messages, duplicates_removed, source_name, bin_filter=None, bank_filter=None):
    if unique_messages:
        file_name = f"x{len(unique_messages)}_results.txt"
        async with aiofiles.open(file_name, mode='w') as f:
            await f.write("\n".join(unique_messages))
        user_link = await get_user_link(message)
        caption = (
            f"<b>CC Scrapped Successful ✅</b>\n"
            f"<b>━━━━━━━━━━━━━━━━</b>\n"
            f"<b>Source:</b> <code>{source_name} 🌐</code>\n"
            f"<b>Amount:</b> <code>{len(unique_messages)} 📝</code>\n"
            f"<b>Duplicates Removed:</b> <code>{duplicates_removed} 🗑️</code>\n"
        )
        if bin_filter:
            caption += f"<b>📝 BIN Filter:</b> <code>{bin_filter}</code>\n"
        if bank_filter:
            caption += f"<b>📝 Bank Filter:</b> <code>{bank_filter}</code>\n"
        caption += (
            f"<b>━━━━━━━━━━━━━━━━</b>\n"
            f"<b>✅ Card-Scrapped By: {user_link}</b>\n"
        )
        try:
            LOGGER.info(f"Attempting to send document {file_name} to chat {message.chat.id}")
            await SmartAIO.send_document(
                chat_id=message.chat.id,
                document=FSInputFile(file_name),
                caption=caption,
                parse_mode=SmartParseMode.HTML
            )
            LOGGER.info(f"Successfully sent document {file_name} to chat {message.chat.id}")
            await delete_messages(message.chat.id, [message.message_id])
        except Exception as e:
            LOGGER.error(f"Failed to send document {file_name}: {e}")
            await message.edit_text("<b>Sorry Bro ❌ Failed to Send Results</b>")
            await Smart_Notify(bot, f"{BotCommands}scr", e, message)
        finally:
            if os.path.exists(file_name):
                LOGGER.info(f"Removing temporary file {file_name}")
                clean_download(file_name)
    else:
        await message.edit_text("<b>Sorry Bro ❌ No Credit Card Found</b>")
        LOGGER.info("No credit cards found")

async def get_user_link(message):
    if message.from_user and message.chat.type == "private":
        user_first_name = message.from_user.first_name
        user_last_name = message.from_user.last_name or ""
        user_full_name = f"{user_first_name} {user_last_name}".strip()
        return f'<a href="tg://user?id={message.from_user.id}">{user_full_name}</a>'
    else:
        return f'<a href="https://t.me/{message.chat.username or "this_group"}">{message.chat.title}</a>'

async def join_private_chat(client, invite_link):
    try:
        await client.join_chat(invite_link)
        LOGGER.info(f"Joined chat via invite link: {invite_link}")
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
    try:
        await client.join_chat(invite_link)
        LOGGER.info(f"Sent join request to chat: {invite_link}")
        return True
    except PeerIdInvalid as e:
        LOGGER.error(f"Failed to send join request to chat {invite_link}: {e}")
        return False
    except InviteRequestSent:
        LOGGER.info(f"Join request sent to the chat: {invite_link}")
        await message.edit_text("<b>Hey Bro I Have Sent Join Request✅</b>")
        return False

@dp.message(Command(commands=["scr", "ccscr", "scrcc"], prefix=BotCommands))
@new_task
@SmartDefender
async def scr_command(message: Message, bot: Bot):
    args = get_args(message)
    if len(args) < 2:
        await send_message(message.chat.id, "<b>⚠️ Provide channel username and amount to scrape ❌</b>", parse_mode=SmartParseMode.HTML)
        LOGGER.warning("Invalid command: Missing arguments")
        return
    channel_identifier = args[0]
    chat = None
    channel_name = ""
    channel_username = ""
    if channel_identifier.lstrip("-").isdigit():
        chat_id = int(channel_identifier)
        try:
            chat = await SmartUserBot.get_chat(chat_id)
            channel_name = chat.title
            LOGGER.info(f"Scraping from private channel: {channel_name} (ID: {chat_id})")
        except Exception as e:
            await send_message(message.chat.id, "<b>Hey Bro! 🥲 Invalid chat ID ❌</b>", parse_mode=SmartParseMode.HTML)
            LOGGER.error(f"Failed to fetch private channel: {e}")
            return
    else:
        if channel_identifier.startswith("https://t.me/+"):
            invite_link = channel_identifier
            temporary_msg = await send_message(message.chat.id, "<b>Checking Username...✨</b>", parse_mode=SmartParseMode.HTML)
            joined = await join_private_chat(SmartUserBot, invite_link)
            if not joined:
                request_sent = await send_join_request(SmartUserBot, invite_link, temporary_msg)
                if not request_sent:
                    return
            else:
                await delete_messages(message.chat.id, [temporary_msg.message_id])
                chat = await SmartUserBot.get_chat(invite_link)
                channel_name = chat.title
                LOGGER.info(f"Joined private channel via link: {channel_name}")
        elif channel_identifier.startswith("https://t.me/") or channel_identifier.startswith("t.me/"):
            channel_username = channel_identifier.split("t.me/")[-1]
        else:
            channel_username = channel_identifier
        if not chat:
            try:
                chat = await SmartUserBot.get_chat(channel_username)
                channel_name = chat.title
                LOGGER.info(f"Scraping from public channel: {channel_name} (Username: {channel_username})")
            except Exception as e:
                await send_message(message.chat.id, "<b>Hey Bro! 🥲 Incorrect username or chat ID ❌</b>", parse_mode=SmartParseMode.HTML)
                LOGGER.error(f"Failed to fetch public channel: {e}")
                return
    try:
        limit = int(args[1])
        LOGGER.info(f"Scraping limit set to: {limit}")
    except ValueError:
        await send_message(message.chat.id, "<b>⚠️ Invalid limit value. Please provide a valid number ❌</b>", parse_mode=SmartParseMode.HTML)
        LOGGER.warning("Invalid limit value provided")
        return
    start_number = None
    bank_name = None
    bin_filter = None
    if len(args) > 2:
        if args[2].isdigit():
            start_number = args[2]
            bin_filter = args[2][:6]
            LOGGER.info(f"BIN filter applied: {bin_filter}")
        else:
            bank_name = " ".join(args[2:])
            LOGGER.info(f"Bank filter applied: {bank_name}")
    max_lim = SUDO_CCSCR_LIMIT if message.from_user and message.from_user.id in (OWNER_ID if isinstance(OWNER_ID, (list, tuple)) else [OWNER_ID]) else CC_SCRAPPER_LIMIT
    if limit > max_lim:
        await send_message(message.chat.id, f"<b>Sorry Bro! Amount over Max limit is {max_lim} ❌</b>", parse_mode=SmartParseMode.HTML)
        LOGGER.warning(f"Limit exceeded: {limit} > {max_lim}")
        return
    temporary_msg = await send_message(message.chat.id, "<b>Checking The Username...✨</b>", parse_mode=SmartParseMode.HTML)
    await asyncio.sleep(1.5)
    await temporary_msg.edit_text("<b>Scraping In Progress✨</b>")
    scrapped_results = await scrape_messages(SmartUserBot, chat.id, limit, start_number=start_number, bank_name=bank_name)
    unique_messages, duplicates_removed = remove_duplicates(scrapped_results)
    await send_results(bot, temporary_msg, unique_messages, duplicates_removed, channel_name, bin_filter=bin_filter, bank_filter=bank_name)

@dp.message(Command(commands=["mc", "multiscr", "mscr"], prefix=BotCommands))
@new_task
@SmartDefender
async def mc_command(message: Message, bot: Bot):
    args = get_args(message)
    if len(args) < 2:
        await send_message(message.chat.id, "<b>⚠️ Provide at least one channel username</b>", parse_mode=SmartParseMode.HTML)
        LOGGER.warning("Invalid command: Missing arguments")
        return
    channel_identifiers = args[:-1]
    try:
        limit = int(args[-1])
    except ValueError:
        await send_message(message.chat.id, "<b>⚠️ Invalid limit value. Please provide a valid number ❌</b>", parse_mode=SmartParseMode.HTML)
        LOGGER.warning("Invalid limit value provided")
        return
    max_lim = SUDO_CCSCR_LIMIT if message.from_user and message.from_user.id in (OWNER_ID if isinstance(OWNER_ID, (list, tuple)) else [OWNER_ID]) else MULTI_CCSCR_LIMIT
    if limit > max_lim:
        await send_message(message.chat.id, f"<b>Sorry Bro! Amount over Max limit is {max_lim} ❌</b>", parse_mode=SmartParseMode.HTML)
        LOGGER.warning(f"Limit exceeded: {limit} > {max_lim}")
        return
    temporary_msg = await send_message(message.chat.id, "<b>Scraping In Progress✨</b>", parse_mode=SmartParseMode.HTML)
    all_messages = []
    tasks = []
    for channel_identifier in channel_identifiers:
        parsed_url = urlparse(channel_identifier)
        channel_username = parsed_url.path.lstrip('/') if parsed_url.scheme else channel_identifier
        tasks.append(scrape_messages_task(SmartUserBot, channel_username, limit, bot, message))
    results = await asyncio.gather(*tasks)
    for result in results:
        all_messages.extend(result)
    unique_messages, duplicates_removed = remove_duplicates(all_messages)
    unique_messages = unique_messages[:limit]
    await send_results(bot, temporary_msg, unique_messages, duplicates_removed, "Multiple Chats")

async def scrape_messages_task(client, channel_identifier, limit, bot, message):
    try:
        chat = None
        if channel_identifier.startswith("https://t.me/+"):
            invite_link = channel_identifier
            temporary_msg = await send_message(message.chat.id, "<b>Checking Username...</b>", parse_mode=SmartParseMode.HTML)
            joined = await join_private_chat(client, invite_link)
            if not joined:
                request_sent = await send_join_request(client, invite_link, temporary_msg)
                if not request_sent:
                    return []
            else:
                await delete_messages(message.chat.id, [temporary_msg.message_id])
                chat = await client.get_chat(invite_link)
        else:
            chat = await client.get_chat(channel_identifier)
        return await scrape_messages(client, chat.id, limit)
    except Exception as e:
        await send_message(message.chat.id, f"<b>Hey Bro! 🥲 Incorrect username for {channel_identifier} ❌</b>", parse_mode=SmartParseMode.HTML)
        LOGGER.error(f"Failed to scrape from {channel_identifier}: {e}")
        return []