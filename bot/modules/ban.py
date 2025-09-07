# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
#  Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
import asyncio
from datetime import datetime
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from pyrogram.errors import UserIdInvalid, UsernameInvalid, PeerIdInvalid
from pyrogram.enums import ParseMode as SmartParseMode
from bot import dp, SmartPyro
from bot.helpers.botutils import send_message, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.buttons import SmartButtons
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.core.database import SmartGuards, SmartSecurity
from bot.helpers.guard import admin_only
from bot.helpers.security import SmartShield
from config import OWNER_ID

def validate_message(func):
    async def wrapper(message: Message, bot: Bot):
        if not message or not message.from_user:
            LOGGER.error("Invalid message received")
            return
        return await func(message, bot)
    return wrapper

async def resolve_user(identifier: str):
    try:
        if identifier.startswith("@"):
            user = await SmartPyro.get_users(identifier)
            full_name = f"{user.first_name} {user.last_name or ''}".strip()
            username = f"@{user.username}" if user.username else "None"
            return user.id, full_name, username
        else:
            user_id = int(identifier)
            user = await SmartPyro.get_users(user_id)
            full_name = f"{user.first_name} {user.last_name or ''}".strip()
            username = f"@{user.username}" if user.username else "None"
            return user_id, full_name, username
    except (UserIdInvalid, UsernameInvalid, PeerIdInvalid, ValueError) as e:
        await Smart_Notify(SmartPyro, "resolve_user", e)
        LOGGER.error(f"Error resolving user {identifier}: {e}")
        return None, None, None

@dp.message(Command(commands=["ban"], prefix=BotCommands))
@admin_only
@validate_message
async def ban_command(message: Message, bot: Bot):
    args = get_args(message)
    reply = message.reply_to_message
    if not args and not reply:
        await send_message(
            chat_id=message.chat.id,
            text="<b>Please Provide A Valid User To Ban ❌</b>",
            parse_mode=SmartParseMode.HTML
        )
        return

    target_user_id = None
    full_name = None
    username = None
    reason = "undefined"

    if reply and reply.from_user:
        target_user_id = reply.from_user.id
        full_name = reply.from_user.full_name or str(target_user_id)
        username = f"@{reply.from_user.username}" if reply.from_user.username else "None"
        if args:
            reason = " ".join(args)
    else:
        identifier = args[0]
        if len(args) > 1:
            reason = " ".join(args[1:])
        target_user_id, full_name, username = await resolve_user(identifier)

    if not target_user_id:
        await send_message(
            chat_id=message.chat.id,
            text="<b>Please Provide A Valid User To Ban ❌</b>",
            parse_mode=SmartParseMode.HTML
        )
        return

    if target_user_id == OWNER_ID:
        await send_message(
            chat_id=message.chat.id,
            text="<b>Lol I Can Not Ban My Creator ❌</b>",
            parse_mode=SmartParseMode.HTML
        )
        return

    progress_message = await send_message(
        chat_id=message.chat.id,
        text="<b>Banning User From Smart Tools...</b>",
        parse_mode=SmartParseMode.HTML
    )
    await asyncio.sleep(1)

    try:
        if await SmartSecurity.find_one({"user_id": target_user_id}):
            await progress_message.edit_text(
                text="<b>Sorry Failed To Ban User From Bot ❌</b>",
                parse_mode=SmartParseMode.HTML
            )
            return
    except Exception as e:
        await progress_message.edit_text(
            text="<b>Sorry Failed To Ban User From Bot ❌</b>",
            parse_mode=SmartParseMode.HTML
        )
        await Smart_Notify(bot, "ban_command_check_ban", e, message)
        LOGGER.error(f"Error checking ban status for {target_user_id}: {e}")
        return

    ban_date = datetime.utcnow()
    try:
        await SmartSecurity.insert_one({
            "user_id": target_user_id,
            "username": username,
            "full_name": full_name,
            "ban_date": ban_date,
            "reason": reason
        })
        LOGGER.info(f"Banned user {target_user_id} with reason {reason}")
    except Exception as e:
        await progress_message.edit_text(
            text="<b>Sorry Failed To Ban User From Bot ❌</b>",
            parse_mode=SmartParseMode.HTML
        )
        await Smart_Notify(bot, "ban_command_insert", e, message)
        LOGGER.error(f"Error banning user {target_user_id}: {e}")
        return

    await SmartShield(bot, target_user_id, message)

    ban_date_str = ban_date.strftime("%Y-%m-%d %H:%M:%S")
    try:
        await progress_message.edit_text(
            text=(
                f"<b>{full_name} [<code>{target_user_id}</code>] banned.</b>\n"
                f"<b>Reason:</b> {reason}\n"
                f"<b>Ban Date:</b> {ban_date_str}"
            ),
            parse_mode=SmartParseMode.HTML
        )
    except Exception as e:
        await Smart_Notify(bot, "ban_command_edit", e, message)
        LOGGER.error(f"Failed to edit progress message: {e}")
        await send_message(
            chat_id=message.chat.id,
            text=(
                f"<b>{full_name} [<code>{target_user_id}</code>] banned.</b>\n"
                f"<b>Reason:</b> {reason}\n"
                f"<b>Ban Date:</b> {ban_date_str}"
            ),
            parse_mode=SmartParseMode.HTML
        )

    try:
        admin_list = await SmartGuards.find({}, {"user_id": 1, "_id": 0}).to_list(None)
        AUTH_ADMIN_IDS = [admin["user_id"] for admin in admin_list]
        for admin_id in [OWNER_ID] + AUTH_ADMIN_IDS:
            if admin_id != message.from_user.id and isinstance(admin_id, int):
                await send_message(
                    chat_id=admin_id,
                    text=(
                        f"<b>{full_name} [<code>{target_user_id}</code>] banned.</b>\n"
                        f"<b>Reason:</b> {reason}\n"
                        f"<b>Ban Date:</b> {ban_date_str}"
                    ),
                    parse_mode=SmartParseMode.HTML
                )
    except Exception as e:
        await Smart_Notify(bot, "ban_command_notify_admins", e, message)
        LOGGER.error(f"Error notifying admins: {e}")

@dp.message(Command(commands=["unban"], prefix=BotCommands))
@admin_only
@validate_message
async def unban_command(message: Message, bot: Bot):
    args = get_args(message)
    reply = message.reply_to_message
    if not args and not reply:
        await send_message(
            chat_id=message.chat.id,
            text="<b>Please Provide A Valid User To Unban ❌</b>",
            parse_mode=SmartParseMode.HTML
        )
        return

    target_user_id = None
    full_name = None
    username = None

    if reply and reply.from_user:
        target_user_id = reply.from_user.id
        full_name = reply.from_user.full_name or str(target_user_id)
        username = f"@{reply.from_user.username}" if reply.from_user.username else "None"
    else:
        identifier = args[0]
        target_user_id, full_name, username = await resolve_user(identifier)

    if not target_user_id:
        await send_message(
            chat_id=message.chat.id,
            text="<b>Please Provide A Valid User To Unban ❌</b>",
            parse_mode=SmartParseMode.HTML
        )
        return

    progress_message = await send_message(
        chat_id=message.chat.id,
        text="<b>Unbanning User From Smart Tools...</b>",
        parse_mode=SmartParseMode.HTML
    )
    await asyncio.sleep(1)

    try:
        if not await SmartSecurity.find_one({"user_id": target_user_id}):
            await progress_message.edit_text(
                text="<b>Sorry Failed To Unban User From Bot ❌</b>",
                parse_mode=SmartParseMode.HTML
            )
            return
    except Exception as e:
        await progress_message.edit_text(
            text="<b>Sorry Failed To Unban User From Bot ❌</b>",
            parse_mode=SmartParseMode.HTML
        )
        await Smart_Notify(bot, "unban_command_check_ban", e, message)
        LOGGER.error(f"Error checking ban status for {target_user_id}: {e}")
        return

    try:
        result = await SmartSecurity.delete_one({"user_id": target_user_id})
        if result.deleted_count == 0:
            await progress_message.edit_text(
                text="<b>Sorry Failed To Unban User From Bot ❌</b>",
                parse_mode=SmartParseMode.HTML
            )
            LOGGER.info(f"User {target_user_id} not found for unban")
            return
        LOGGER.info(f"Unbanned user {target_user_id}")
    except Exception as e:
        await progress_message.edit_text(
            text="<b>Sorry Failed To Unban User From Bot ❌</b>",
            parse_mode=SmartParseMode.HTML
        )
        await Smart_Notify(bot, "unban_command_delete", e, message)
        LOGGER.error(f"Error unbanning user {target_user_id}: {e}")
        return

    profile_link = f"tg://user?id={target_user_id}"
    try:
        await progress_message.edit_text(
            text=f"<b> Successfully Unbanned <a href='{profile_link}'>{full_name}</a> From Smart Tools ✅</b>",
            parse_mode=SmartParseMode.HTML
        )
    except Exception as e:
        await Smart_Notify(bot, "unban_command_edit", e, message)
        LOGGER.error(f"Failed to edit progress message: {e}")
        await send_message(
            chat_id=message.chat.id,
            text=f"<b> Successfully Unbanned <a href='{profile_link}'>{full_name}</a> From Smart Tools ✅</b>",
            parse_mode=SmartParseMode.HTML
        )

    await send_message(
        chat_id=target_user_id,
        text="<b>Good News, You Can Now Use Me ✅</b>",
        parse_mode=SmartParseMode.HTML
    )

    try:
        admin_list = await SmartGuards.find({}, {"user_id": 1, "_id": 0}).to_list(None)
        AUTH_ADMIN_IDS = [admin["user_id"] for admin in admin_list]
        for admin_id in [OWNER_ID] + AUTH_ADMIN_IDS:
            if admin_id != message.from_user.id and isinstance(admin_id, int):
                await send_message(
                    chat_id=admin_id,
                    text=f"<b>Successfully Unbanned <a href='{profile_link}'>{full_name}</a> From Smart Tools ✅</b>",
                    parse_mode=SmartParseMode.HTML
                )
    except Exception as e:
        await Smart_Notify(bot, "unban_command_notify_admins", e, message)
        LOGGER.error(f"Error notifying admins: {e}")

@dp.message(Command(commands=["banlist"], prefix=BotCommands))
@admin_only
@validate_message
async def banlist_command(message: Message, bot: Bot):
    progress_message = await send_message(
        chat_id=message.chat.id,
        text="<b>Fetching Banned List From Database...</b>",
        parse_mode=SmartParseMode.HTML
    )
    await asyncio.sleep(1)

    try:
        banned_list = await SmartSecurity.find({}).to_list(None)
        if not banned_list:
            await progress_message.edit_text(
                text="<b>No Users Are Currently Banned ✅</b>",
                parse_mode=SmartParseMode.HTML
            )
            return

        response = ["<b>🚫 Banned Users List:</b>", "<b>━━━━━━━━━━━━━━━━━</b>"]
        for index, user in enumerate(banned_list, 1):
            reason = user.get("reason", "Undefined")
            ban_date = user.get("ban_date", datetime.utcnow())
            ban_date_str = ban_date.strftime("%Y-%m-%d %H:%M:%S")
            response.extend([
                f"<b>{index}. {user['full_name']} [<code>{user['user_id']}</code>]</b>",
                f"<b>⊗ Username:</b> {user['username']}",
                f"<b>⊗ Reason:</b> {reason}",
                f"<b>⊗ Ban Date:</b> {ban_date_str}",
                "<b>━━━━━━━━━━━━━━━━━</b>"
            ])

        response.append(f"<b>Total Banned Users: {len(banned_list)} ✅</b>")
        buttons = SmartButtons()
        buttons.button(text="✘ Close", callback_data="close_banlist$", position="footer")
        reply_markup = buttons.build_menu(b_cols=1, f_cols=1)

        await progress_message.edit_text(
            text="\n".join(response),
            parse_mode=SmartParseMode.HTML,
            reply_markup=reply_markup
        )
    except Exception as e:
        await progress_message.edit_text(
            text="<b>Sorry Failed To Show Database ❌</b>",
            parse_mode=SmartParseMode.HTML
        )
        await Smart_Notify(bot, "banlist_command_fetch", e, message)
        LOGGER.error(f"Error fetching banned users list: {e}")

@dp.callback_query(lambda c: c.data == "close_banlist$")
@admin_only
async def handle_close_callback(query: CallbackQuery, bot: Bot):
    try:
        await query.message.delete()
        await query.answer()
    except Exception as e:
        await Smart_Notify(bot, "close_banlist", e)
        LOGGER.error(f"Error deleting message: {e}")
        await query.answer("❌ Failed to close!", show_alert=True)