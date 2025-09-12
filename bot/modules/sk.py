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
from bot.helpers.defend import SmartDefender
from config import A360APIBASEURL
import pycountry

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
                account_info = data.get("account_info", {})
                balance = data.get("balance", {})
                capabilities = data.get("capabilities", {})
        
        country_code = account_info.get('country', 'N/A').upper()
        country_mappings = {'UK': 'GB', 'GB': 'GB', 'UAE': 'AE', 'AE': 'AE'}
        normalized_country_code = country_mappings.get(country_code, country_code)
        
        try:
            country = pycountry.countries.get(alpha_2=normalized_country_code)
            country_name = country.name if country else normalized_country_code
            country_flag = country.flag if country else ''
        except Exception:
            country_name = normalized_country_code
            country_flag = ''
        
        country_payment_key = next((key for key in capabilities if '_intl_payments' in key), None)
        country_payment_status = capabilities.get(country_payment_key, 'N/A') if country_payment_key else 'N/A'
        
        details = (
            f"<b>み SK Key Authentication ↝ Successful ✅</b>\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>⊗ Secret Key ↝</b> <code>{stripe_key}</code>\n"
            f"<b>⊗ Public Key ↝</b> <code>{account_info.get('pk_live', 'N/A')}</code>\n"
            f"<b>⊗ SK Key Status ↝</b> {account_info.get('status', 'N/A')}\n"
            f"<b>⊗ Account ID ↝</b> <code>{account_info.get('account_id', 'N/A')}</code>\n"
            f"<b>⊗ Email ↝</b> <code>{account_info.get('email', 'N/A')}</code>\n"
            f"<b>⊗ Business Name ↝</b> <code>{account_info.get('business_name', 'N/A')}</code>\n"
            f"<b>⊗ Phone ↝</b> <code>{account_info.get('phone', 'N/A')}</code>\n"
            f"<b>⊗ Website ↝</b> <code>{account_info.get('website', 'N/A')}</code>\n"
            f"<b>⊗ Country ↝</b> {country_flag} <code>{country_name}</code>\n"
            f"<b>⊗ Charges Enabled ↝</b> {account_info.get('charges_enabled', 'N/A')}\n"
            f"<b>⊗ Payouts Enabled ↝</b> {account_info.get('payouts_enabled', 'N/A')}\n"
            f"<b>⊗ Account Type ↝</b> <code>{account_info.get('account_type', 'N/A')}</code>\n"
            f"<b>⊗ Card Payments ↝</b> {capabilities.get('card_payments', 'N/A')}\n"
            f"<b>⊗ {country_name} Intl Payments ↝</b> {country_payment_status}\n"
            f"<b>⊗ Transfers ↝</b> {capabilities.get('transfers', 'N/A')}\n"
            f"<b>⊗ Available Balance ↝</b> <code>{balance.get('available', 'N/A')}</code>\n"
            f"<b>⊗ Pending Balance ↝</b> <code>{balance.get('pending', 'N/A')}</code>\n"
            f"<b>⊗ Live Mode ↝</b> {balance.get('live_mode', 'N/A')}\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>⌁ Thank You For Using Smart Tool ↯</b>"
        )
        return details
    except Exception as e:
        logger.error(f"Error fetching Stripe key info: {e}")
        return "SK KEY REVOKED ❌"

@dp.message(Command(commands=["sk"], prefix=BotCommands))
@new_task
@SmartDefender
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
            response_text = (
                f"<b>⊗ SK ➺</b> <code>{stripe_key}</code>\n"
                f"<b>⊗ Response: LIVE KEY ✅</b>\n"
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
@SmartDefender
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
