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
from bot.core.database import SmartGuards
from config import OWNER_ID

async def get_auth_admins():
    try:
        admins = await SmartGuards.find({}, {
            "user_id": 1, "title": 1, "auth_date": 1, "username": 1,
            "full_name": 1, "auth_time": 1, "auth_by": 1, "_id": 0
        }).to_list(None)
        return {admin["user_id"]: {
            "title": admin["title"],
            "auth_date": admin["auth_date"],
            "username": admin.get("username", "None"),
            "full_name": admin.get("full_name", "Unknown"),
            "auth_time": admin.get("auth_time", datetime.utcnow()),
            "auth_by": admin.get("auth_by", "Unknown")
        } for admin in admins}
    except Exception as e:
        await Smart_Notify(SmartPyro, "get_auth_admins", e)
        LOGGER.error(f"Error fetching auth admins: {e}")
        return {}

async def add_auth_admin(user_id: int, title: str, username: str, full_name: str, auth_by: str):
    try:
        auth_time = datetime.utcnow()
        await SmartGuards.update_one(
            {"user_id": user_id},
            {"$set": {
                "user_id": user_id,
                "title": title,
                "auth_date": auth_time,
                "auth_time": auth_time,
                "username": username,
                "full_name": full_name,
                "auth_by": auth_by
            }},
            upsert=True
        )
        LOGGER.info(f"Added/Updated admin {user_id} with title {title}")
        return True
    except Exception as e:
        await Smart_Notify(SmartPyro, "add_auth_admin", e)
        LOGGER.error(f"Error adding/updating admin {user_id}: {e}")
        return False

async def remove_auth_admin(user_id: int):
    try:
        result = await SmartGuards.delete_one({"user_id": user_id})
        if result.deleted_count > 0:
            LOGGER.info(f"Removed admin {user_id}")
            return True
        else:
            LOGGER.info(f"Admin {user_id} not found for removal")
            return False
    except Exception as e:
        await Smart_Notify(SmartPyro, "remove_auth_admin", e)
        LOGGER.error(f"Error removing admin {user_id}: {e}")
        return False

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

@dp.message(Command(commands=["getadmins"], prefix=BotCommands))
async def get_admins_command(message: Message, bot: Bot):
    user_id = message.from_user.id
    if user_id != OWNER_ID:
        return

    progress_message = await send_message(
        chat_id=message.chat.id,
        text="<b>Fetching Smart Tools Admins List...</b>",
        parse_mode=SmartParseMode.HTML
    )
    await asyncio.sleep(1)

    admin_list = [
        "<b>Smart Tools Admins List ✅</b>",
        "<b>━━━━━━━━━━━━━━━━━</b>"
    ]

    try:
        owner_user = await SmartPyro.get_users(OWNER_ID)
        owner_full_name = f"{owner_user.first_name} {owner_user.last_name or ''}".strip()
        owner_username = f"@{owner_user.username}" if owner_user.username else "None"
        owner_profile_link = f"tg://user?id={OWNER_ID}"

        admin_list.extend([
            f"<b>⊗ Name:</b> {owner_full_name}",
            f"<b>⊗ Title:</b> Owner",
            f"<b>⊗ Username:</b> {owner_username}",
            f"<b>⊗ User ID:</b> <code>{OWNER_ID}</code>",
            f"<b>⊗ Auth Time:</b> Infinity",
            f"<b>⊗ Auth Date:</b> Infinity",
            f"<b>⊗ Auth By:</b> <a href='{owner_profile_link}'>{owner_full_name}</a>",
            "<b>━━━━━━━━━━━━━━━━━</b>"
        ])
    except Exception as e:
        await Smart_Notify(bot, "get_admins_owner", e, message)
        admin_list.extend([
            f"<b>⊗ Name:</b> ID {OWNER_ID} (Not found)",
            f"<b>⊗ Title:</b> Owner",
            f"<b>⊗ Username:</b> None",
            f"<b>⊗ User ID:</b> <code>{OWNER_ID}</code>",
            f"<b>⊗ Auth Time:</b> Infinity",
            f"<b>⊗ Auth Date:</b> Infinity",
            f"<b>⊗ Auth By:</b> Unknown",
            "<b>━━━━━━━━━━━━━━━━━</b>"
        ])

    auth_admins_data = await get_auth_admins()
    total_admins = 1

    for admin_id, data in auth_admins_data.items():
        try:
            user = await SmartPyro.get_users(admin_id)
            full_name = f"{user.first_name} {user.last_name or ''}".strip()
            username = f"@{user.username}" if user.username else "None"
            profile_link = f"tg://user?id={admin_id}"

            auth_time = data["auth_time"]
            time_str = auth_time.strftime("%H:%M:%S")
            auth_date = auth_time.strftime("%Y-%m-%d")

            try:
                owner_user = await SmartPyro.get_users(OWNER_ID)
                owner_full_name = f"{owner_user.first_name} {owner_user.last_name or ''}".strip()
                owner_profile_link = f"tg://user?id={OWNER_ID}"
                auth_by_text = f"<a href='{owner_profile_link}'>{owner_full_name}</a>"
            except:
                auth_by_text = "Unknown"

            admin_list.extend([
                f"<b>⊗ Name:</b> {full_name}",
                f"<b>⊗ Title:</b> {data['title']}",
                f"<b>⊗ Username:</b> {username}",
                f"<b>⊗ User ID:</b> <code>{admin_id}</code>",
                f"<b>⊗ Auth Time:</b> {time_str}",
                f"<b>⊗ Auth Date:</b> {auth_date}",
                f"<b>⊗ Auth By:</b> {auth_by_text}",
                "<b>━━━━━━━━━━━━━━━━━</b>"
            ])
            total_admins += 1
        except Exception as e:
            await Smart_Notify(bot, "get_admins_loop", e, message)
            auth_time = data["auth_time"]
            time_str = auth_time.strftime("%H:%M:%S")
            auth_date = auth_time.strftime("%Y-%m-%d")

            admin_list.extend([
                f"<b>⊗ Name:</b> ID {admin_id} (Not found)",
                f"<b>⊗ Title:</b> {data['title']}",
                f"<b>⊗ Username:</b> {data.get('username', 'None')}",
                f"<b>⊗ User ID:</b> <code>{admin_id}</code>",
                f"<b>⊗ Auth Time:</b> {time_str}",
                f"<b>⊗ Auth Date:</b> {auth_date}",
                f"<b>⊗ Auth By:</b> Unknown",
                "<b>━━━━━━━━━━━━━━━━━</b>"
            ])
            total_admins += 1

    admin_list.append(f"<b>Total Smart Tools Admins: {total_admins} ✅</b>")

    buttons = SmartButtons()
    buttons.button(text="✘ Close", callback_data="close_admins$")
    reply_markup = buttons.build_menu(b_cols=1)

    try:
        await progress_message.edit_text(
            text="\n".join(admin_list),
            parse_mode=SmartParseMode.HTML,
            reply_markup=reply_markup
        )
    except Exception as e:
        await Smart_Notify(bot, "get_admins_edit", e, message)
        LOGGER.error(f"Failed to edit progress message: {e}")
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Failed to display admin list!</b>",
            parse_mode=SmartParseMode.HTML
        )

@dp.message(Command(commands=["auth"], prefix=BotCommands))
async def auth_command(message: Message, bot: Bot):
    user_id = message.from_user.id
    if user_id != OWNER_ID:
        return

    args = get_args(message)
    if not args:
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Please specify a valid user to promote!</b>",
            parse_mode=SmartParseMode.HTML
        )
        return

    identifier = args[0]
    title = args[1] if len(args) > 1 else "Admin"

    target_user_id, full_name, username = await resolve_user(identifier)
    if not target_user_id:
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Please specify a valid user to promote!</b>",
            parse_mode=SmartParseMode.HTML
        )
        return

    if target_user_id == OWNER_ID or target_user_id in await get_auth_admins():
        await send_message(
            chat_id=message.chat.id,
            text="<b>This User Is Already One Of The Staff To Control Me 😐</b>",
            parse_mode=SmartParseMode.HTML
        )
        return

    progress_message = await send_message(
        chat_id=message.chat.id,
        text="<b>Promoting user to authorized users...</b>",
        parse_mode=SmartParseMode.HTML
    )
    await asyncio.sleep(1)

    try:
        owner_user = await SmartPyro.get_users(OWNER_ID)
        auth_by = f"{owner_user.first_name} {owner_user.last_name or ''}".strip()
    except Exception as e:
        await Smart_Notify(bot, "auth_owner_resolve", e, message)
        auth_by = "Unknown"

    if await add_auth_admin(target_user_id, title, username, full_name, auth_by):
        profile_link = f"tg://user?id={target_user_id}"
        try:
            await progress_message.edit_text(
                text=f"<b>✅ Successfully promoted <a href='{profile_link}'>{full_name}</a>!</b>",
                parse_mode=SmartParseMode.HTML
            )
        except Exception as e:
            await Smart_Notify(bot, "auth_edit", e, message)
            LOGGER.error(f"Failed to edit progress message: {e}")
            await send_message(
                chat_id=message.chat.id,
                text=f"<b>✅ Successfully promoted <a href='{profile_link}'>{full_name}</a>!</b>",
                parse_mode=SmartParseMode.HTML
            )
    else:
        try:
            await progress_message.edit_text(
                text="<b>❌ Failed to promote user!</b>",
                parse_mode=SmartParseMode.HTML
            )
        except Exception as e:
            await Smart_Notify(bot, "auth_edit", e, message)
            LOGGER.error(f"Failed to edit progress message: {e}")
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Failed to promote user!</b>",
                parse_mode=SmartParseMode.HTML
            )

@dp.message(Command(commands=["unauth"], prefix=BotCommands))
async def unauth_command(message: Message, bot: Bot):
    user_id = message.from_user.id
    if user_id != OWNER_ID:
        return

    args = get_args(message)
    if not args:
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Please specify a valid user to demote!</b>",
            parse_mode=SmartParseMode.HTML
        )
        return

    identifier = args[0]
    target_user_id, full_name, username = await resolve_user(identifier)
    if not target_user_id:
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Please specify a valid user to demote!</b>",
            parse_mode=SmartParseMode.HTML
        )
        return

    if target_user_id == OWNER_ID:
        await send_message(
            chat_id=message.chat.id,
            text="<b>I Can Not Unauthorize My Creator ❌</b>",
            parse_mode=SmartParseMode.HTML
        )
        return

    progress_message = await send_message(
        chat_id=message.chat.id,
        text="<b>Demoting user from authorized users...</b>",
        parse_mode=SmartParseMode.HTML
    )
    await asyncio.sleep(1)

    if await remove_auth_admin(target_user_id):
        profile_link = f"tg://user?id={target_user_id}"
        try:
            await progress_message.edit_text(
                text=f"<b>✅ Successfully demoted <a href='{profile_link}'>{full_name}</a>!</b>",
                parse_mode=SmartParseMode.HTML
            )
        except Exception as e:
            await Smart_Notify(bot, "unauth_edit", e, message)
            LOGGER.error(f"Failed to edit progress message: {e}")
            await send_message(
                chat_id=message.chat.id,
                text=f"<b>✅ Successfully demoted <a href='{profile_link}'>{full_name}</a>!</b>",
                parse_mode=SmartParseMode.HTML
            )
    else:
        try:
            await progress_message.edit_text(
                text="<b>❌ Failed to demote user!</b>",
                parse_mode=SmartParseMode.HTML
            )
        except Exception as e:
            await Smart_Notify(bot, "unauth_edit", e, message)
            LOGGER.error(f"Failed to edit progress message: {e}")
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Failed to demote user!</b>",
                parse_mode=SmartParseMode.HTML
            )

@dp.callback_query(lambda c: c.data == "close_admins$")
async def handle_close_callback(query: CallbackQuery, bot: Bot):
    user_id = query.from_user.id
    if user_id != OWNER_ID:
        return

    try:
        await query.message.delete()
        await query.answer()
    except Exception as e:
        await Smart_Notify(bot, "close_admins", e)
        LOGGER.error(f"Error deleting message: {e}")
        await query.answer("❌ Failed to close!", show_alert=True)