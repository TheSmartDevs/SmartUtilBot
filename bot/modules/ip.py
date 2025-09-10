import aiohttp
import asyncio
import ipaddress
import socket
import urllib.parse
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

async def resolve_to_ip(target: str) -> str:
    target = (target or "").strip()
    if not target:
        raise ValueError("Empty target")
    try:
        parsed = urllib.parse.urlparse(target)
        host = parsed.netloc if parsed.netloc else parsed.path
    except Exception:
        host = target
    if "@" in host:
        host = host.split("@", 1)[-1]
    if host.startswith("[") and "]" in host:
        host = host[1:host.index("]")]
    if ":" in host and host.count(":") == 1 and not host.startswith("["):
        host = host.split(":", 1)[0]
    try:
        ipaddress.ip_address(host)
        return host
    except Exception:
        pass
    loop = asyncio.get_running_loop()
    infos = await loop.getaddrinfo(host, None, family=socket.AF_UNSPEC, proto=socket.IPPROTO_TCP)
    chosen_ip = None
    for fam, _type, _proto, _canon, sockaddr in infos:
        candidate = sockaddr[0]
        if ":" not in candidate:
            chosen_ip = candidate
            break
        if chosen_ip is None:
            chosen_ip = candidate
    if not chosen_ip:
        raise Exception(f"could not resolve host {host} to an IP")
    return chosen_ip

async def get_ip_info(target_ip: str, bot: Bot) -> str:
    url = f"https://ipinfo.io/{target_ip}/json"
    headers = {"Authorization": f"Bearer {IPINFO_API_TOKEN}"} if IPINFO_API_TOKEN else {}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                data = await response.json()
        ip_from_api = data.get("ip", target_ip)
        asn = data.get("org", "Unknown")
        isp = data.get("org", "Unknown")
        country = data.get("country", "Unknown")
        city = data.get("city", "Unknown")
        timezone = data.get("timezone", "Unknown")
        fraud_score_value = data.get("fraud_score") or data.get("fraud", {}).get("score")
        if fraud_score_value is None:
            fraud_score_str = "N/A"
            risk_level = "N/A"
        else:
            try:
                fraud_score_float = float(fraud_score_value)
                fraud_score_str = str(int(fraud_score_float)) if fraud_score_float.is_integer() else str(fraud_score_float)
                risk_level = "low" if fraud_score_float < 50 else "high"
            except Exception:
                fraud_score_str = str(fraud_score_value)
                risk_level = "N/A"
        details = (
            f"<b>YOUR IP INFORMATION 🌐</b>\n"
            f"<b>━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>IP:</b> <code>{ip_from_api}</code>\n"
            f"<b>ASN:</b> <code>{asn}</code>\n"
            f"<b>ISP:</b> <code>{isp}</code>\n"
            f"<b>Country City:</b> <code>{country} {city}</code>\n"
            f"<b>Timezone:</b> <code>{timezone}</code>\n"
            f"<b>IP Fraud Score:</b> <code>{fraud_score_str}</code>\n"
            f"<b>Risk LEVEL:</b> <code>{risk_level} Risk</code>\n"
            f"<b>━━━━━━━━━━━━━━━━━━</b>\n"
        )
        return details
    except aiohttp.ClientError as e:
        logger.error(f"Failed to fetch IP info for {target_ip}: {e}")
        await Smart_Notify(bot, "/ip", e, None)
        return "<b>Invalid IP address or API error</b>"
    except Exception as e:
        logger.error(f"Unexpected error fetching IP info for {target_ip}: {e}")
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
            text="<b>❌ Please provide a single IP address or URL/hostname.</b>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        return
    target = args[0].strip()
    fetching_msg = await send_message(
        chat_id=message.chat.id,
        text="<b>Fetching IP Info Please Wait.....✨</b>",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )
    try:
        try:
            resolved_ip = await resolve_to_ip(target)
            logger.info(f"Resolved target '{target}' to IP {resolved_ip}")
        except Exception as e:
            logger.error(f"Failed to resolve target '{target}': {e}")
            try:
                await SmartAIO.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=fetching_msg.message_id,
                    text="<b>❌ Could not resolve the domain or invalid IP</b>",
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
                    text="<b>❌ Could not resolve the domain or invalid IP</b>",
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
            return
        details = await get_ip_info(resolved_ip, bot)
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
        logger.error(f"Error processing IP info for {target}: {e}")
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
