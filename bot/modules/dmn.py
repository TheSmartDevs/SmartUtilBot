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
from config import DOMAIN_API_KEY, DOMAIN_API_URL, DOMAIN_CHK_LIMIT

logger = LOGGER

async def format_date(date_str):
    return date_str

async def get_domain_info(domain: str, bot: Bot) -> str:
    params = {
        "apiKey": DOMAIN_API_KEY,
        "domainName": domain,
        "outputFormat": "JSON"
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(DOMAIN_API_URL, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                logger.info(f"Response for domain {domain}: {data}")
                if data.get("WhoisRecord"):
                    whois_record = data["WhoisRecord"]
                    status = whois_record.get("status", "Unknown").lower()
                    data_error = whois_record.get("dataError", "")
                    registrar = whois_record.get("registrarName", "Unknown")
                    registration_date = await format_date(whois_record.get("createdDate", "Unknown"))
                    expiration_date = await format_date(whois_record.get("expiresDate", "Unknown"))
                    if status == "available" or data_error == "MISSING_WHOIS_DATA" or not whois_record.get("registryData"):
                        return (
                            f"<b>Smart A360 Domain Check Results...✅</b>\n"
                            f"<b>━━━━━━━━━━━━━━━━━━</b>\n"
                            f"<b>Domain : </b><code>{domain}</code>\n"
                            f"<b>Congrats !🥳 This Domain Is Available. ✅</b>\n"
                            f"<b>━━━━━━━━━━━━━━━━━━</b>"
                        )
                    else:
                        return (
                            f"<b>Smart A360 Domain Check Results...✅</b>\n"
                            f"<b>━━━━━━━━━━━━━━━━━━</b>\n"
                            f"<b>Domain : </b><code>{domain}</code>\n"
                            f"<b>Registrar : </b><code>{registrar}</code>\n"
                            f"<b>Registration Date : </b><code>{registration_date}</code>\n"
                            f"<b>Expiration Date : </b><code>{expiration_date}</code>\n"
                            f"<b>━━━━━━━━━━━━━━━━━━</b>"
                        )
                else:
                    return (
                        f"<b>Smart A360 Domain Check Results...✅</b>\n"
                        f"<b>━━━━━━━━━━━━━━━━━━</b>\n"
                        f"<b>Domain : </b><code>{domain}</code>\n"
                        f"<b>Congrats !🥳 This Domain Is Available. ✅</b>\n"
                        f"<b>━━━━━━━━━━━━━━━━━━</b>"
                    )
    except aiohttp.ClientError as e:
        logger.error(f"Failed to fetch info for domain {domain}: {e}")
        await Smart_Notify(bot, "/dmn", e, None)
        return f"<b>❌ Sorry Bro Domain API Dead</b>"
    except Exception as e:
        logger.error(f"Exception occurred while fetching info for domain {domain}: {e}")
        await Smart_Notify(bot, "/dmn", e, None)
        return f"<b>❌ Sorry Bro Domain Check API Dead</b>"

@dp.message(Command(commands=["dmn", ".dmn"], prefix=BotCommands))
@new_task
async def domain_info(message: Message, bot: Bot):
    if message.chat.type not in [ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP]:
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ This command only works in private or group chats</b>",
            parse_mode=ParseMode.HTML
        )
        return
    user_id = message.from_user.id
    logger.info(f"Command received from user {user_id} in chat {message.chat.id}: {message.text}")
    domains = get_args(message)
    if not domains:
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Please provide at least one valid domain name.</b>",
            parse_mode=ParseMode.HTML
        )
        return
    if len(domains) > DOMAIN_CHK_LIMIT:
        await send_message(
            chat_id=message.chat.id,
            text=f"<b>❌ You can check up to {DOMAIN_CHK_LIMIT} domains at a time.</b>",
            parse_mode=ParseMode.HTML
        )
        return
    progress_message = await send_message(
        chat_id=message.chat.id,
        text="<b>Fetching domain information...✨</b>",
        parse_mode=ParseMode.HTML
    )
    try:
        results = await asyncio.gather(*[get_domain_info(domain, bot) for domain in domains], return_exceptions=True)
        result_message = []
        for domain, result in zip(domains, results):
            if isinstance(result, Exception):
                logger.error(f"Error processing domain {domain}: {result}")
                await Smart_Notify(bot, "/dmn", result, message)
                result_message.append(f"<b>❌ {domain}: Failed to check domain</b>")
            else:
                result_message.append(result)
        if message.from_user:
            user_full_name = f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
            user_info = f"\n<b>Domain Info Grab By :</b> <a href=\"tg://user?id={message.from_user.id}\">{user_full_name}</a>"
        else:
            group_name = message.chat.title or "this group"
            group_url = f"https://t.me/{message.chat.username}" if message.chat.username else "this group"
            user_info = f"\n<b>Domain Info Grab By :</b> <a href=\"{group_url}\">{group_name}</a>"
        result_message = "\n\n".join(result_message) + user_info
        try:
            await progress_message.edit_text(
                text=result_message,
                parse_mode=ParseMode.HTML
            )
        except Exception:
            await delete_messages(
                chat_id=message.chat.id,
                message_ids=[progress_message.message_id]
            )
            await send_message(
                chat_id=message.chat.id,
                text=result_message,
                parse_mode=ParseMode.HTML
            )
    except Exception as e:
        logger.error(f"Error processing domain check: {e}")
        await Smart_Notify(bot, "/dmn", e, message)
        try:
            await progress_message.edit_text(
                text="<b>❌ Sorry Bro Domain Check API Dead</b>",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            await delete_messages(
                chat_id=message.chat.id,
                message_ids=[progress_message.message_id]
            )
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Sorry Bro Domain Check API Dead</b>",
                parse_mode=ParseMode.HTML
            )
