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

async def get_domain_info(domain: str, bot: Bot) -> str:
    url = f"{A360APIBASEURL}/dmn"
    params = {"domain": domain}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params) as response:
                response.raise_for_status()
                data = await response.json()
                logger.info(f"Response for domain {domain}: {data}")
                domain_name = data.get("domain", domain)
                if data.get("registered_on") is None:
                    return (
                        f"<b>Smart A360 Domain Check Results...✅</b>\n"
                        f"<b>━━━━━━━━━━━━━━━━━━</b>\n"
                        f"<b>Domain : </b><code>{html.escape(domain_name)}</code>\n"
                        f"<b>Congrats !🥳 This Domain Is Available. ✅</b>\n"
                        f"<b>━━━━━━━━━━━━━━━━━━</b>"
                    )
                else:
                    registrar = data.get("registrar", "Unknown")
                    registered_on = data.get("registered_on", "Unknown")
                    expires_on = data.get("expires_on", "Unknown")
                    return (
                        f"<b>Smart A360 Domain Check Results...✅</b>\n"
                        f"<b>━━━━━━━━━━━━━━━━━━</b>\n"
                        f"<b>Domain : </b><code>{html.escape(domain_name)}</code>\n"
                        f"<b>Registrar : </b><code>{html.escape(registrar)}</code>\n"
                        f"<b>Registration Date : </b><code>{html.escape(registered_on)}</code>\n"
                        f"<b>Expiration Date : </b><code>{html.escape(expires_on)}</code>\n"
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
        result_message = []
        for domain, result in zip(domains, results):
            if isinstance(result, Exception):
                logger.error(f"Error processing domain {domain}: {result}")
                await Smart_Notify(bot, "/dmn", result, message)
                result_message.append(f"<b>❌ {html.escape(domain)}: Failed to check domain</b>")
            else:
                result_message.append(result)
        if message.from_user:
            user_full_name = f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
            user_info = f"\n<b>Domain Info Grab By :</b> <a href=\"tg://user?id={message.from_user.id}\">{html.escape(user_full_name)}</a>"
        else:
            group_name = message.chat.title or "this group"
            group_url = f"https://t.me/{message.chat.username}" if message.chat.username else "this group"
            user_info = f"\n<b>Domain Info Grab By :</b> <a href=\"{group_url}\">{html.escape(group_name)}</a>"
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