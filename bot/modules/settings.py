import asyncio
import os
from aiogram import Bot, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from pyrogram.enums import ParseMode as SmartParseMode
from bot import dp, SmartPyro
from bot.helpers.botutils import send_message, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.buttons import SmartButtons
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.guard import admin_only

user_session = {}
settings_lock = asyncio.Lock()
ITEMS_PER_PAGE = 10

def validate_message(func):
    async def wrapper(message: Message, bot: Bot):
        if not message or not message.from_user:
            LOGGER.error("Invalid message received")
            return
        return await func(message, bot)
    return wrapper

def detect_duplicate_keys():
    try:
        with open(".env") as f:
            lines = f.readlines()
            seen_keys = set()
            duplicates = set()
            for line in lines:
                if '=' in line:
                    key = line.split("=", 1)[0].strip()
                    if key in seen_keys:
                        duplicates.add(key)
                    seen_keys.add(key)
            if duplicates:
                LOGGER.warning(f"Duplicate keys found in .env: {', '.join(duplicates)}")
    except Exception as e:
        LOGGER.error(f"Error detecting duplicate keys in .env: {e}")

def load_env_vars():
    try:
        with open(".env") as f:
            lines = f.readlines()
            variables = {}
            seen_keys = set()
            for line in lines:
                if '=' in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    if key not in seen_keys:
                        variables[key] = value
                        seen_keys.add(key)
            return variables
    except Exception as e:
        LOGGER.error(f"Error loading environment variables: {e}")
        return {}

async def update_env_var(key, value):
    async with settings_lock:
        try:
            env_vars = load_env_vars()
            env_vars[key] = value
            os.environ[key] = value
            with open(".env", "w") as f:
                for k, v in env_vars.items():
                    f.write(f"{k}={v}\n")
            LOGGER.info(f"Updated environment variable: {key}")
        except Exception as e:
            LOGGER.error(f"Error updating environment variable {key}: {e}")

config_keys = load_env_vars()

async def build_menu(page=0):
    keys = list(config_keys.keys())
    start, end = page * ITEMS_PER_PAGE, (page + 1) * ITEMS_PER_PAGE
    current_keys = keys[start:end]
    buttons = SmartButtons()
    for i in range(0, len(current_keys), 2):
        buttons.button(text=current_keys[i], callback_data=f"settings_edit_{current_keys[i]}")
        if i + 1 < len(current_keys):
            buttons.button(text=current_keys[i + 1], callback_data=f"settings_edit_{current_keys[i + 1]}")
    if page > 0:
        buttons.button(text="⬅️ Previous", callback_data=f"settings_page_{page - 1}", position="footer")
    if end < len(keys):
        buttons.button(text="Next ➡️", callback_data=f"settings_page_{page + 1}", position="footer")
    buttons.button(text="Close ❌", callback_data="settings_closesettings", position="footer")
    return buttons.build_menu(b_cols=2, f_cols=2)

@dp.message(Command(commands=["settings"], prefix=BotCommands))
@validate_message
@admin_only
async def show_settings(message: Message, bot: Bot):
    try:
        await send_message(
            chat_id=message.chat.id,
            text="<b>Select a change or edit 👇</b>",
            parse_mode=SmartParseMode.HTML,
            reply_markup=await build_menu()
        )
        LOGGER.info(f"Settings command initiated by user_id {message.from_user.id}")
    except Exception as e:
        await Smart_Notify(bot, "show_settings", e, message)
        LOGGER.error(f"Failed to show settings for user_id {message.from_user.id}: {e}")
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Failed to display settings!</b>",
            parse_mode=SmartParseMode.HTML
        )

@dp.callback_query(lambda c: c.data.startswith("settings_page_"))
async def paginate_menu(query: CallbackQuery, bot: Bot):
    from bot.core.database import SmartGuards
    from config import OWNER_ID
    user_id = query.from_user.id
    auth_admins_data = await SmartGuards.find({}, {"user_id": 1, "_id": 0}).to_list(None)
    AUTH_ADMIN_IDS = [admin["user_id"] for admin in auth_admins_data]
    if user_id != OWNER_ID and user_id not in AUTH_ADMIN_IDS:
        LOGGER.info(f"Unauthorized pagination attempt by user_id {user_id}")
        return
    try:
        page = int(query.data.split("_")[2])
        await query.message.edit_reply_markup(reply_markup=await build_menu(page))
        await query.answer()
        LOGGER.debug(f"Paginated to page {page} by user_id {user_id}")
    except Exception as e:
        await Smart_Notify(bot, "paginate_menu", e)
        LOGGER.error(f"Failed to paginate settings for user_id {user_id}: {e}")
        await query.answer("❌ Failed to paginate!", show_alert=True)

@dp.callback_query(lambda c: c.data.startswith("settings_edit_"))
async def edit_var(query: CallbackQuery, bot: Bot):
    from bot.core.database import SmartGuards
    from config import OWNER_ID
    user_id = query.from_user.id
    auth_admins_data = await SmartGuards.find({}, {"user_id": 1, "_id": 0}).to_list(None)
    AUTH_ADMIN_IDS = [admin["user_id"] for admin in auth_admins_data]
    if user_id != OWNER_ID and user_id not in AUTH_ADMIN_IDS:
        LOGGER.info(f"Unauthorized edit attempt by user_id {user_id}")
        return
    var_name = query.data.split("_", 2)[2]
    if var_name not in config_keys:
        await query.answer("Invalid variable selected.", show_alert=True)
        LOGGER.warning(f"Invalid variable {var_name} selected by user_id {user_id}")
        return
    user_session[user_id] = {
        "var": var_name,
        "chat_id": query.message.chat.id
    }
    buttons = SmartButtons()
    buttons.button(text="Cancel ❌", callback_data="settings_cancel_edit")
    reply_markup = buttons.build_menu(b_cols=1)
    try:
        await query.message.edit_text(
            text=f"<b>Editing <code>{var_name}</code>. Please send the new value below with a prefix (e.g., .value).</b>",
            parse_mode=SmartParseMode.HTML,
            reply_markup=reply_markup
        )
        LOGGER.info(f"User_id {user_id} started editing variable {var_name}")
    except Exception as e:
        await Smart_Notify(bot, "edit_var", e)
        LOGGER.error(f"Failed to edit variable {var_name} for user_id {user_id}: {e}")
        await query.answer("❌ Failed to start editing!", show_alert=True)

@dp.callback_query(lambda c: c.data == "settings_cancel_edit")
async def cancel_edit(query: CallbackQuery, bot: Bot):
    from bot.core.database import SmartGuards
    from config import OWNER_ID
    user_id = query.from_user.id
    auth_admins_data = await SmartGuards.find({}, {"user_id": 1, "_id": 0}).to_list(None)
    AUTH_ADMIN_IDS = [admin["user_id"] for admin in auth_admins_data]
    if user_id != OWNER_ID and user_id not in AUTH_ADMIN_IDS:
        LOGGER.info(f"Unauthorized cancel edit attempt by user_id {user_id}")
        return
    user_session.pop(user_id, None)
    try:
        await query.message.edit_text(
            text="<b>Variable Editing Cancelled ❌</b>",
            parse_mode=SmartParseMode.HTML
        )
        await query.answer()
        LOGGER.info(f"User_id {user_id} cancelled variable editing")
    except Exception as e:
        await Smart_Notify(bot, "cancel_edit", e)
        LOGGER.error(f"Failed to cancel edit for user_id {user_id}: {e}")
        await query.answer("❌ Failed to cancel!", show_alert=True)

@dp.callback_query(lambda c: c.data == "settings_closesettings")
async def close_menu(query: CallbackQuery, bot: Bot):
    from bot.core.database import SmartGuards
    from config import OWNER_ID
    user_id = query.from_user.id
    auth_admins_data = await SmartGuards.find({}, {"user_id": 1, "_id": 0}).to_list(None)
    AUTH_ADMIN_IDS = [admin["user_id"] for admin in auth_admins_data]
    if user_id != OWNER_ID and user_id not in AUTH_ADMIN_IDS:
        LOGGER.info(f"Unauthorized close menu attempt by user_id {user_id}")
        return
    try:
        await query.message.edit_text(
            text="<b>Closed Settings Menu ✅</b>",
            parse_mode=SmartParseMode.HTML
        )
        await query.answer()
        LOGGER.info(f"User_id {user_id} closed settings menu")
    except Exception as e:
        await Smart_Notify(bot, "close_menu", e)
        LOGGER.error(f"Failed to close settings menu for user_id {user_id}: {e}")
        await query.answer("❌ Failed to close!", show_alert=True)

@dp.message(lambda message: F.text & any(message.text.startswith(prefix) for prefix in BotCommands))
@validate_message
@admin_only
async def update_value(message: Message, bot: Bot):
    LOGGER.debug(f"Received message for update_value: user_id={message.from_user.id}, text={message.text}, chat_id={message.chat.id}")
    session = user_session.get(message.from_user.id)
    if not session or session["chat_id"] != message.chat.id:
        LOGGER.debug(f"Rejected update_value for user_id {message.from_user.id}: session={session}, chat_id={message.chat.id}")
        return
    message_text = message.text or message.caption
    if not message_text:
        LOGGER.debug(f"No valid text in message for user_id {message.from_user.id}")
        await send_message(
            chat_id=message.chat.id,
            text="<b>Please provide a text value to update with a prefix (e.g., .value) ❌</b>",
            parse_mode=SmartParseMode.HTML
        )
        return
    val = message_text.strip()
    for prefix in BotCommands:
        if val.startswith(prefix):
            val = val[len(prefix):].strip()
            break
    LOGGER.debug(f"Processed input for user_id {message.from_user.id}: raw={message_text}, stripped={val}")
    if not val:
        LOGGER.debug(f"Empty value after stripping prefix for user_id {message.from_user.id}")
        await send_message(
            chat_id=message.chat.id,
            text="<b>Please provide a non-empty value after the prefix (e.g., .value) ❌</b>",
            parse_mode=SmartParseMode.HTML
        )
        return
    var = session["var"]
    try:
        await update_env_var(var, val)
        config_keys[var] = val
        await send_message(
            chat_id=message.chat.id,
            text=f"<b><code>{var}</code> Has Been Successfully Updated To <code>{val}</code>. ✅</b>",
            parse_mode=SmartParseMode.HTML
        )
        user_session.pop(message.from_user.id, None)
        LOGGER.info(f"User_id {message.from_user.id} updated variable {var} to {val}")
    except Exception as e:
        await Smart_Notify(bot, "update_value", e, message)
        LOGGER.error(f"Failed to update variable {var} for user_id {message.from_user.id}: {e}")
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Failed to update variable!</b>",
            parse_mode=SmartParseMode.HTML
        )

detect_duplicate_keys()