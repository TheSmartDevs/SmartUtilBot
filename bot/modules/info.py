from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode, ChatType
from bot import dp, SmartAIO, SmartPyro
from bot.helpers.utils import new_task
from bot.helpers.botutils import send_message, delete_messages
from bot.helpers.logger import LOGGER
from bot.helpers.buttons import SmartButtons
from bot.helpers.dcutil import SmartDCLocate
from bot.helpers.commands import BotCommands
from pyrogram.errors import PeerIdInvalid, UsernameNotOccupied, ChannelInvalid

logger = LOGGER

def calculate_account_age(creation_date):
    today = datetime.now()
    delta = relativedelta(today, creation_date)
    years = delta.years
    months = delta.months
    days = delta.days
    return f"{years} years, {months} months, {days} days"

def estimate_account_creation_date(user_id):
    reference_points = [
        (100000000, datetime(2013, 8, 1)),
        (1273841502, datetime(2020, 8, 13)),
        (1500000000, datetime(2021, 5, 1)),
        (2000000000, datetime(2022, 12, 1)),
    ]
    
    closest_point = min(reference_points, key=lambda x: abs(x[0] - user_id))
    closest_user_id, closest_date = closest_point
    
    id_difference = user_id - closest_user_id
    days_difference = id_difference / 20000000
    creation_date = closest_date + timedelta(days=days_difference)
    
    return creation_date

@dp.message(Command(commands=["info", "id"], prefix=BotCommands))
@new_task
async def handle_info_command(message: Message, bot: Bot):
    if message.chat.type not in [ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP]:
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ This command only works in private or group chats</b>",
            parse_mode=ParseMode.HTML
        )
        return

    logger.info("Received /info or /id command")
    progress_message = await send_message(
        chat_id=message.chat.id,
        text="<code>Processing User Info...</code>",
        parse_mode=ParseMode.HTML
    )
    DC_LOCATIONS = SmartDCLocate()

    try:
        if not message.text.split() or (len(message.text.split()) == 1 and not message.reply_to_message):
            logger.info("Fetching current user info")
            user = await SmartPyro.get_users(message.from_user.id)
            chat = await SmartPyro.get_chat(message.chat.id)
            premium_status = "Yes" if user.is_premium else "No"
            dc_location = DC_LOCATIONS.get(user.dc_id, "Unknown")
            account_created = estimate_account_creation_date(user.id)
            account_created_str = account_created.strftime("%B %d, %Y")
            account_age = calculate_account_age(account_created)
            
            verified_status = "Verified" if getattr(user, 'is_verified', False) else "Not Verified"
            
            chat_id_display = chat.id if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP] else user.id
            full_name = f"{user.first_name} {user.last_name or ''}".strip()
            response = (
                "<b>🔍 Showing User's Profile Info 📋</b>\n"
                "<b>━━━━━━━━━━━━━━━━</b>\n"
                f"<b>Full Name:</b> <b>{full_name}</b>\n"
            )
            if user.username:
                response += f"<b>Username:</b> @{user.username}\n"
            response += (
                f"<b>User ID:</b> <code>{user.id}</code>\n"
                f"<b>Chat ID:</b> <code>{chat_id_display}</code>\n"
                f"<b>Premium User:</b> <b>{premium_status}</b>\n"
                f"<b>Data Center:</b> <b>{dc_location}</b>\n"
                f"<b>Created On:</b> <b>{account_created_str}</b>\n"
                f"<b>Account Age:</b> <b>{account_age}</b>\n"
                "<b>━━━━━━━━━━━━━━━━</b>\n"
                "<b>👁 Thank You for Using Our Tool ✅</b>"
            )
            buttons = SmartButtons()
            buttons.button(text=full_name, copy_text=str(user.id))
            await SmartAIO.edit_message_text(
                chat_id=message.chat.id,
                message_id=progress_message.message_id,
                text=response,
                parse_mode=ParseMode.HTML,
                reply_markup=buttons.build_menu(b_cols=1)
            )
            logger.info("User info fetched successfully with buttons")

        elif message.reply_to_message:
            logger.info("Fetching info of the replied user or bot")
            user = await SmartPyro.get_users(message.reply_to_message.from_user.id)
            chat = await SmartPyro.get_chat(message.chat.id)
            premium_status = "Yes" if user.is_premium else "No"
            dc_location = DC_LOCATIONS.get(user.dc_id, "Unknown")
            account_created = estimate_account_creation_date(user.id)
            account_created_str = account_created.strftime("%B %d, %Y")
            account_age = calculate_account_age(account_created)
            
            verified_status = "Verified" if getattr(user, 'is_verified', False) else "Not Verified"
            
            chat_id_display = chat.id if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP] else user.id
            full_name = f"{user.first_name} {user.last_name or ''}".strip()
            if user.is_bot:
                response = (
                    "<b>🔍 Showing Bot's Profile Info 📋</b>\n"
                    "<b>━━━━━━━━━━━━━━━━</b>\n"
                    f"<b>Bot Name:</b> <b>{full_name}</b>\n"
                )
                if user.username:
                    response += f"<b>Username:</b> @{user.username}\n"
                response += (
                    f"<b>User ID:</b> <code>{user.id}</code>\n"
                    f"<b>Data Center:</b> <b>{dc_location}</b>\n"
                    "<b>━━━━━━━━━━━━━━━━</b>\n"
                    "<b>👁 Thank You for Using Our Tool ✅</b>"
                )
            else:
                response = (
                    "<b>🔍 Showing User's Profile Info 📋</b>\n"
                    "<b>━━━━━━━━━━━━━━━━</b>\n"
                    f"<b>Full Name:</b> <b>{full_name}</b>\n"
                )
                if user.username:
                    response += f"<b>Username:</b> @{user.username}\n"
                response += (
                    f"<b>User ID:</b> <code>{user.id}</code>\n"
                    f"<b>Chat ID:</b> <code>{chat_id_display}</code>\n"
                    f"<b>Premium User:</b> <b>{premium_status}</b>\n"
                    f"<b>Data Center:</b> <b>{dc_location}</b>\n"
                    f"<b>Created On:</b> <b>{account_created_str}</b>\n"
                    f"<b>Account Age:</b> <b>{account_age}</b>\n"
                    "<b>━━━━━━━━━━━━━━━━</b>\n"
                    "<b>👁 Thank You for Using Our Tool ✅</b>"
                )
            buttons = SmartButtons()
            buttons.button(text=full_name, copy_text=str(user.id))
            await SmartAIO.edit_message_text(
                chat_id=message.chat.id,
                message_id=progress_message.message_id,
                text=response,
                parse_mode=ParseMode.HTML,
                reply_markup=buttons.build_menu(b_cols=1)
            )
            logger.info("Replied user info fetched successfully")

        elif len(message.text.split()) > 1:
            logger.info("Extracting username from the command")
            username = message.text.split()[1].strip('@').replace('https://', '').replace('http://', '').replace('t.me/', '').replace('/', '').replace(':', '')

            try:
                logger.info(f"Fetching info for user or bot: {username}")
                user = await SmartPyro.get_users(username)
                premium_status = "Yes" if user.is_premium else "No"
                dc_location = DC_LOCATIONS.get(user.dc_id, "Unknown")
                account_created = estimate_account_creation_date(user.id)
                account_created_str = account_created.strftime("%B %d, %Y")
                account_age = calculate_account_age(account_created)
                
                verified_status = "Verified" if user.is_verified else "Not Verified"
                
                full_name = f"{user.first_name} {user.last_name or ''}".strip()
                if user.is_bot:
                    response = (
                        "<b>🔍 Showing Bot's Profile Info 📋</b>\n"
                        "<b>━━━━━━━━━━━━━━━━</b>\n"
                        f"<b>Bot Name:</b> <b>{full_name}</b>\n"
                    )
                    if user.username:
                        response += f"<b>Username:</b> @{user.username}\n"
                    response += (
                        f"<b>User ID:</b> <code>{user.id}</code>\n"
                        f"<b>Data Center:</b> <b>{dc_location}</b>\n"
                        "<b>━━━━━━━━━━━━━━━━</b>\n"
                        "<b>👁 Thank You for Using Our Tool ✅</b>"
                    )
                else:
                    response = (
                        "<b>🔍 Showing User's Profile Info 📋</b>\n"
                        "<b>━━━━━━━━━━━━━━━━</b>\n"
                        f"<b>Full Name:</b> <b>{full_name}</b>\n"
                    )
                    if user.username:
                        response += f"<b>Username:</b> @{user.username}\n"
                    response += (
                        f"<b>User ID:</b> <code>{user.id}</code>\n"
                        f"<b>Chat ID:</b> <code>{user.id}</code>\n"
                        f"<b>Premium User:</b> <b>{premium_status}</b>\n"
                        f"<b>Data Center:</b> <b>{dc_location}</b>\n"
                        f"<b>Created On:</b> <b>{account_created_str}</b>\n"
                        f"<b>Account Age:</b> <b>{account_age}</b>\n"
                        "<b>━━━━━━━━━━━━━━━━</b>\n"
                        "<b>👁 Thank You for Using Our Tool ✅</b>"
                    )
                buttons = SmartButtons()
                buttons.button(text=full_name, copy_text=str(user.id))
                await SmartAIO.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=progress_message.message_id,
                    text=response,
                    parse_mode=ParseMode.HTML,
                    reply_markup=buttons.build_menu(b_cols=1)
                )
                logger.info("User/bot info fetched successfully with buttons")
            except (PeerIdInvalid, UsernameNotOccupied, IndexError):
                logger.info(f"Username '{username}' not found as a user/bot. Checking for chat...")
                try:
                    chat = await SmartPyro.get_chat(username)
                    dc_location = DC_LOCATIONS.get(chat.dc_id, "Unknown")
                    chat_type = "Channel" if chat.type == ChatType.CHANNEL else "Group" if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP] else "Unknown"
                    full_name = chat.title
                    response = (
                        f"<b>🔍 Showing {chat_type}'s Profile Info 📋</b>\n"
                        "<b>━━━━━━━━━━━━━━━━</b>\n"
                        f"<b>Full Name:</b> <b>{full_name}</b>\n"
                    )
                    if chat.username:
                        response += f"<b>Username:</b> @{chat.username}\n"
                    response += (
                        f"<b>Chat ID:</b> <code>{chat.id}</code>\n"
                        f"<b>Total Members:</b> <b>{chat.members_count if chat.members_count else 'Unknown'}</b>\n"
                        "<b>━━━━━━━━━━━━━━━━</b>\n"
                        "<b>👁 Thank You for Using Our Tool ✅</b>"
                    )
                    buttons = SmartButtons()
                    buttons.button(text=full_name, copy_text=str(chat.id))
                    await SmartAIO.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=progress_message.message_id,
                        text=response,
                        parse_mode=ParseMode.HTML,
                        reply_markup=buttons.build_menu(b_cols=1)
                    )
                    logger.info("Chat info fetched successfully with buttons")
                except (ChannelInvalid, PeerIdInvalid):
                    error_message = (
                        "<b>Looks Like I Don't Have Control Over The Channel</b>"
                        if chat_type == "Channel"
                        else "<b>Looks Like I Don't Have Control Over The Group</b>"
                    )
                    await SmartAIO.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=progress_message.message_id,
                        text=error_message,
                        parse_mode=ParseMode.HTML
                    )
                    logger.error(f"Permission error: {error_message}")
                except Exception as e:
                    logger.error(f"Error fetching chat info: {str(e)}")
                    await SmartAIO.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=progress_message.message_id,
                        text="<b>Looks Like I Don't Have Control Over The Group</b>",
                        parse_mode=ParseMode.HTML
                    )
            except Exception as e:
                logger.error(f"Error fetching user or bot info: {str(e)}")
                await SmartAIO.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=progress_message.message_id,
                    text="<b>Looks Like I Don't Have Control Over The User</b>",
                    parse_mode=ParseMode.HTML
                )
    except Exception as e:
        logger.error(f"Unhandled exception: {str(e)}")
        await SmartAIO.edit_message_text(
            chat_id=message.chat.id,
            message_id=progress_message.message_id,
            text="<b>Looks Like I Don't Have Control Over The User</b>",
            parse_mode=ParseMode.HTML
        )