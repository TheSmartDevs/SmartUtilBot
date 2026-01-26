import aiohttp
import asyncio
import html
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
from config import A360APIBASEURL, DOMAIN_CHK_LIMIT

logger = LOGGER

def format_date(date_str: str) -> str:
    if not date_str or date_str == "Unknown":
        return "Unknown"
    try:
        return date_str.split('T')[0]
    except Exception:
        return date_str

async def get_domain_info(domain: str, bot: Bot) -> dict:
    url = f"{A360APIBASEURL}/dmn"
    params = {"domain": domain}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as response:
                response.raise_for_status()
                data = await response.json()
                logger.info(f"Response for domain {domain}: {data}")
                return data
    except aiohttp.ClientError as e:
        logger.error(f"Failed to fetch info for domain {domain}: {e}")
        await Smart_Notify(bot, "/dmn", e, None)
        return None
    except Exception as e:
        logger.error(f"Exception occurred while fetching info for domain {domain}: {e}")
        await Smart_Notify(bot, "/dmn", e, None)
        return None

def format_single_domain(data: dict, domain: str) -> str:
    if not data:
        return f"{html.escape(domain)} <b>Failed to fetch data</b> ❌\n\n"
    
    domain_name = data.get("domain", domain)
    available = data.get("available", None)
    
    if available is True or available == "true":
        return f"{html.escape(domain_name)} <b>Domain is available! ✅</b>\n\n"
    
    registered_on = data.get("registered_on")
    
    if not registered_on or registered_on == "Unknown":
        return f"{html.escape(domain_name)} <b>Domain is available! ✅</b>\n\n"
    
    registrar = data.get("registrar", "Unknown")
    expires_on = data.get("expires_on", "Unknown")
    
    registered_formatted = format_date(registered_on)
    expires_formatted = format_date(expires_on)
    
    return (
        f"<b>Domain:</b> {html.escape(domain_name)}\n"
        f"<b>Registrar:</b> {html.escape(registrar)}\n"
        f"<b>Registered:</b> {html.escape(registered_formatted)}\n"
        f"<b>Expires:</b> {html.escape(expires_formatted)}\n\n"
    )

@dp.message(Command(commands=["dmn", ".dmn"], prefix=BotCommands))
@new_task
@SmartDefender
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
        
        domain_results = []
        for domain, result in zip(domains, results):
            if isinstance(result, Exception):
                logger.error(f"Error processing domain {domain}: {result}")
                await Smart_Notify(bot, "/dmn", result, message)
                domain_results.append(f"{html.escape(domain)} <b>Failed to check domain</b> ❌\n\n")
            else:
                domain_results.append(format_single_domain(result, domain))
        
        result_message = "".join(domain_results)
        
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