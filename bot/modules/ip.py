# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
#  Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
import aiohttp
import asyncio
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode, ChatType
from bot import dp, SmartAIO
from bot.helpers.utils import new_task
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.notify import Smart_Notify
from bot.helpers.logger import LOGGER
from bot.helpers.commands import BotCommands
from bot.helpers.defend import SmartDefender
from config import IPINFO_API_TOKEN

logger = LOGGER

async def get_ip_info(ip: str, bot: Bot) -> str:
    url = f"https://ipinfo.io/{ip}/json"
    headers = {"Authorization": f"Bearer {IPINFO_API_TOKEN}"}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                data = await response.json()
        ip = data.get("ip", "Unknown")
        asn = data.get("org", "Unknown")
        isp = data.get("org", "Unknown")
        country = data.get("country", "Unknown")
        city = data.get("city", "Unknown")
        timezone = data.get("timezone", "Unknown")
        fraud_score = 0
        risk_level = "low" if fraud_score < 50 else "high"
        details = (
            f"<b>YOUR IP INFORMATION 🌐</b>\n"
            f"<b>━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>IP:</b> <code>{ip}</code>\n"
            f"<b>ASN:</b> <code>{asn}</code>\n"
            f"<b>ISP:</b> <code>{isp}</code>\n"
            f"<b>Country City:</b> <code>{country} {city}</code>\n"
            f"<b>Timezone:</b> <code>{timezone}</code>\n"
            f"<b>IP Fraud Score:</b> <code>{fraud_score}</code>\n"
            f"<b>Risk LEVEL:</b> <code>{risk_level} Risk</code>\n"
            f"<b>━━━━━━━━━━━━━━━━━━</b>\n"
        )
        return details
    except aiohttp.ClientError as e:
        logger.error(f"Failed to fetch IP info for {ip}: {e}")
        await Smart_Notify(bot, "/ip", e, None)
        return "<b>Invalid IP address or API error</b>"
    except Exception as e:
        logger.error(f"Unexpected error fetching IP info for {ip}: {e}")
        await Smart_Notify(bot, "/ip", e, None)
        return "<b>Invalid IP address or API error</b>"

@dp.message(Command(commands=["ip", ".ip"], prefix=BotCommands))
@new_task
@SmartDefender
async def ip_info(message: Message, bot: Bot):
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
    args = get_args(message)
    if len(args) != 1:
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Please provide a single IP address.</b>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        return
    ip = args[0]
    fetching_msg = await send_message(
        chat_id=message.chat.id,
        text="<b>Fetching IP Info Please Wait.....✨</b>",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )
    try:
        details = await get_ip_info(ip, bot)
        if details.startswith("<b>Invalid"):
            raise Exception("Failed to retrieve IP information")
        if message.from_user:
            user_full_name = f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
            user_info = f"\n<b>Ip-Info Grab By:</b> <a href=\"tg://user?id={message.from_user.id}\">{user_full_name}</a>"
        else:
            group_name = message.chat.title or "this group"
            group_url = f"https://t.me/{message.chat.username}" if message.chat.username else "this group"
            user_info = f"\n<b>Ip-Info Grab By:</b> <a href=\"{group_url}\">{group_name}</a>"
        details += user_info
        try:
            await SmartAIO.edit_message_text(
                chat_id=message.chat.id,
                message_id=fetching_msg.message_id,
                text=details,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        except Exception:
            await delete_messages(
                chat_id=message.chat.id,
                message_ids=[fetching_msg.message_id]
            )
            await send_message(
                chat_id=message.chat.id,
                text=details,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
    except Exception as e:
        logger.error(f"Error processing IP info for {ip}: {e}")
        await Smart_Notify(bot, "/ip", e, message)
        try:
            await SmartAIO.edit_message_text(
                chat_id=message.chat.id,
                message_id=fetching_msg.message_id,
                text="<b>❌ Sorry Bro IP Info API Dead</b>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        except Exception:
            await delete_messages(
                chat_id=message.chat.id,
                message_ids=[fetching_msg.message_id]
            )
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Sorry Bro IP Info API Dead</b>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )