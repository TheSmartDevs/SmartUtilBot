import aiohttp
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
from config import A360APIBASEURL

logger = LOGGER

async def verify_stripe_key(stripe_key: str) -> dict:
    url = f"{A360APIBASEURL}/sk/chk?key={stripe_key}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.json()
                logger.info(f"Stripe key check response: {data}")
                if response.status == 200 and data.get("success") and data.get("data", {}).get("status") == "Live":
                    return {"status": "LIVE KEY ✅", "data": data.get("data", {})}
                return {"status": "SK KEY REVOKED ❌", "data": {}}
    except Exception as e:
        logger.error(f"Error verifying Stripe key: {e}")
        return {"status": "SK KEY REVOKED ❌", "data": {}}

async def get_stripe_key_info(stripe_key: str) -> str:
    url = f"{A360APIBASEURL}/sk/info?key={stripe_key}"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status != 200 or not (data := await response.json()).get("success"):
                    return "SK KEY REVOKED ❌"
                data = data.get("data", {})
        available_balance = data.get("available_balance", 0) / 100 if data.get("available_balance") else 0
        currency = data.get("currency", "N/A").upper()
        details = (
            f"<b>み SK Key Authentication ↝ Successful ✅</b>\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>⊗ SK Key Status ↝</b> {'Live ✅' if data.get('charges_enabled') else 'Restricted ❌'}\n"
            f"<b>⊗ Account ID ↝</b> <code>{data.get('id', 'N/A')}</code>\n"
            f"<b>⊗ Email ↝</b> <code>{data.get('email', 'N/A')}</code>\n"
            f"<b>⊗ Business Name ↝</b> <code>{data.get('business_name', 'N/A')}</code>\n"
            f"<b>⊗ Charges Enabled ↝</b> {'Yes ✅' if data.get('charges_enabled') else 'No ❌'}\n"
            f"<b>⊗ Payouts Enabled ↝</b> {'Yes ✅' if data.get('payouts_enabled') else 'No ❌'}\n"
            f"<b>⊗ Account Type ↝</b> <code>{data.get('type', 'N/A').capitalize()}</code>\n"
            f"<b>⊗ Balance ↝</b> <code>{available_balance} {currency}</code>\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>⌁ Thank You For Using Smart Tool ↯</b>"
        )
        return details
    except Exception as e:
        logger.error(f"Error fetching Stripe key info: {e}")
        return "SK KEY REVOKED ❌"

@dp.message(Command(commands=["sk"], prefix=BotCommands))
@new_task
async def stripe_key_handler(message: Message, bot: Bot):
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
    if not args:
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Please provide a Stripe key. Usage: /sk [Stripe Key]</b>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        return
    stripe_key = args[0]
    fetching_msg = await send_message(
        chat_id=message.chat.id,
        text="<b>Processing Your Request...✨</b>",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )
    try:
        result = await verify_stripe_key(stripe_key)
        user_full_name = f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
        user_link = f"<a href=\"tg://user?id={user_id}\">{user_full_name}</a>"
        if result["status"] == "SK KEY REVOKED ❌":
            response_text = (
                f"<b>⊗ SK ➺</b> <code>{stripe_key}</code>\n"
                f"<b>⊗ Response: SK KEY REVOKED ❌</b>\n"
                f"<b>⊗ Checked By ➺</b> {user_link}"
            )
        else:
            data = result["data"]
            available_balance = data.get("available_balance", 0) / 100 if data.get("available_balance") else 0
            pending_balance = data.get("pending_balance", 0) / 100 if data.get("pending_balance") else 0
            currency = data.get("currency", "N/A").upper()
            response_text = (
                f"<b>⊗ SK ➺</b> <code>{stripe_key}</code>\n"
                f"<b>⊗ Response: LIVE KEY ✅</b>\n"
                f"<b>⊗ Currency:</b> <code>{currency}</code>\n"
                f"<b>⊗ Available Balance:</b> <code>{available_balance}$</code>\n"
                f"<b>⊗ Pending Balance:</b> <code>{pending_balance}$</code>\n"
                f"<b>⊗ Checked By ➺</b> {user_link}"
            )
        try:
            await fetching_msg.edit_text(
                text=response_text,
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
                text=response_text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
    except Exception as e:
        logger.error(f"Error in stripe_key_handler: {e}")
        await Smart_Notify(bot, "/sk", e, message)
        user_full_name = f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
        user_link = f"<a href=\"tg://user?id={user_id}\">{user_full_name}</a>"
        response_text = (
            f"<b>⊗ SK ➺</b> <code>{stripe_key}</code>\n"
            f"<b>⊗ Response: SK KEY REVOKED ❌</b>\n"
            f"<b>⊗ Checked By ➺</b> {user_link}"
        )
        try:
            await fetching_msg.edit_text(
                text=response_text,
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
                text=response_text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )

@dp.message(Command(commands=["skinfo"], prefix=BotCommands))
@new_task
async def stripe_key_info_handler(message: Message, bot: Bot):
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
    if not args:
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Please provide a Stripe key. Usage: /skinfo [Stripe Key]</b>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        return
    stripe_key = args[0]
    fetching_msg = await send_message(
        chat_id=message.chat.id,
        text="<b>Processing Your Request...✨</b>",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )
    try:
        result = await get_stripe_key_info(stripe_key)
        user_full_name = f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
        user_link = f"<a href=\"tg://user?id={user_id}\">{user_full_name}</a>"
        if result == "SK KEY REVOKED ❌":
            response_text = (
                f"<b>⊗ SK ➺</b> <code>{stripe_key}</code>\n"
                f"<b>⊗ Response: SK KEY REVOKED ❌</b>\n"
                f"<b>⊗ Checked By ➺</b> {user_link}"
            )
        else:
            response_text = result
        try:
            await fetching_msg.edit_text(
                text=response_text,
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
                text=response_text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
    except Exception as e:
        logger.error(f"Error in stripe_key_info_handler: {e}")
        await Smart_Notify(bot, "/skinfo", e, message)
        user_full_name = f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip()
        user_link = f"<a href=\"tg://user?id={user_id}\">{user_full_name}</a>"
        response_text = (
            f"<b>⊗ SK ➺</b> <code>{stripe_key}</code>\n"
            f"<b>⊗ Response: SK KEY REVOKED ❌</b>\n"
            f"<b>⊗ Checked By ➺</b> {user_link}"
        )
        try:
            await fetching_msg.edit_text(
                text=response_text,
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
                text=response_text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )