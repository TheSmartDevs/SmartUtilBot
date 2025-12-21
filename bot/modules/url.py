import asyncio
import aiohttp
import re
from typing import Dict
from datetime import datetime
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ParseMode, ChatType
from bot import dp
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.buttons import SmartButtons
from bot.helpers.logger import LOGGER
from bot.helpers.utils import new_task
from bot.helpers.notify import Smart_Notify
from bot.helpers.defend import SmartDefender
from config import A360APIBASEURL 


user_states: Dict[int, Dict] = {}
user_data: Dict[int, Dict] = {}

def get_state(user_id: int) -> str:
    return user_states.get(user_id, {}).get("state", "")

def set_state(user_id: int, state: str):
    if user_id not in user_states:
        user_states[user_id] = {}
    user_states[user_id]["state"] = state

def clear_state(user_id: int):
    user_states.pop(user_id, None)
    user_data.pop(user_id, None)

def get_data(user_id: int) -> Dict:
    return user_data.get(user_id, {})

def set_data(user_id: int, data: Dict):
    user_data[user_id] = data

def is_valid_url(url: str) -> bool:
    regex = re.compile(r'^https?://', re.IGNORECASE)
    return regex.match(url) is not None

def is_valid_slug(slug: str) -> bool:
    return bool(re.match(r'^[a-zA-Z0-9-]+$', slug))

async def create_short_url(session: aiohttp.ClientSession, long_url: str, custom_slug: str = None):
    params = {"url": long_url}
    if custom_slug:
        params["custom_slug"] = custom_slug
    try:
        async with session.get(f"{A360APIBASEURL}/shortner/shorten", params=params) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("success"):
                    return data
            return None
    except Exception as e:
        LOGGER.error(f"API Error creating short URL: {e}")
        return None

async def check_stats(session: aiohttp.ClientSession, short_code: str):
    try:
        async with session.get(f"{A360APIBASEURL}/shortner/stats/{short_code}") as resp:
            if resp.status == 200:
                return await resp.json()
            return None
    except Exception as e:
        LOGGER.error(f"API Error checking stats: {e}")
        return None

async def delete_url(session: aiohttp.ClientSession, short_code: str):
    try:
        async with session.get(f"{A360APIBASEURL}/shortner/delete/{short_code}") as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("success"):
                    return data
            return None
    except Exception as e:
        LOGGER.error(f"API Error deleting URL: {e}")
        return None

def get_welcome_message() -> str:
    return (
        "<b>🔗 Professional URL Shortener</b>\n\n"
        "Send me a long URL to shorten:\n\n"
        "<b>✅ Supported:</b>\n"
        "• Any valid HTTP/HTTPS URL\n"
        "• Social media links\n"
        "• Long tracking URLs\n"
        "• Product pages\n"
        "• Landing pages\n\n"
        "<b>Examples:</b>\n"
        "<code>https://www.example.com/very/long/url/with/parameters?id=123</code>\n\n"
        "<b>Send the URL now!</b>"
    )

def get_customize_message() -> str:
    return (
        "<b>🎨 Customize Your Short URL</b>\n\n"
        "Choose an option:\n\n"
        "<b>✨ Auto-Generated:</b> a random short code\n"
        "<b>✏️ Custom Slug:</b> Choose your own memorable slug\n\n"
        "<b>Example custom slug:</b>\n"
        "<code>https://a360api.up.railway.app/shortner/040CE6</code> → slug is <code>040CE6</code>"
    )

def get_result_message(short_url: str, original_url: str, clicks: int = 0, created: str = None) -> str:
    if created is None:
        created = datetime.now().strftime("%Y-%m-%d")
    
    return (
        f"<b>🔗 Your Shortened URL</b>\n\n"
        f"<b>Short URL:</b> <code>{short_url}</code>\n"
        f"<b>Target URL:</b> <code>{original_url}</code>\n\n"
        f"<b>📊 Statistics:</b>\n"
        f"• <b>Clicks:</b> {clicks}\n"
        f"• <b>Created:</b> {created}\n\n"
        f"Click 🔄 Refresh Stats to update click count"
    )

def get_confirm_delete_message(short_url: str) -> str:
    return (
        f"<b>⚠️ Confirm Deletion</b>\n\n"
        f"Are you sure you want to permanently delete:\n\n"
        f"🔗 <code>{short_url}</code>\n\n"
        f"This action cannot be undone!"
    )

def get_deleted_message(short_url: str) -> str:
    return (
        f"<b>🔗 Your Shortened URL</b>\n\n"
        f"<b>Short URL:</b> <code>{short_url}</code>\n"
        f"<b>Status:</b> ❌ Deleted\n\n"
        f"<b>📊 Statistics:</b>\n"
        f"• This URL has been permanently deleted\n"
        f"• The link no longer works"
    )

def build_cancel_keyboard():
    buttons = SmartButtons()
    buttons.button("❌ Cancel", "url_cancel")
    return buttons.build_menu(b_cols=1)

def build_method_keyboard():
    buttons = SmartButtons()
    buttons.button("✨ Use Auto-Generate", "url_auto")
    buttons.button("✏️ Custom Slug", "url_custom")
    buttons.button("❌ Cancel", "url_cancel", position="footer")
    return buttons.build_menu(b_cols=2, f_cols=1)

def build_result_keyboard(short_url: str):
    buttons = SmartButtons()
    buttons.button("🔄 Refresh Stats", "url_refresh")
    buttons.button("🗑 Delete URL", "url_delete")
    buttons.button("🔗 Open Short URL", url=short_url)
    return buttons.build_menu(b_cols=1)

def build_confirm_delete_keyboard():
    buttons = SmartButtons()
    buttons.button("✅ Yes, Delete", "url_confirm_delete")
    buttons.button("❌ Cancel", "url_cancel_delete")
    return buttons.build_menu(b_cols=2)

@dp.message(Command(commands=["short"], prefix=BotCommands))
@new_task
@SmartDefender
async def short_handler(message: Message, bot: Bot):
    user_id = message.from_user.id
    
    if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await send_message(
            chat_id=message.chat.id,
            text="<b>⚠️ Generate short URLs in private chat</b>",
            parse_mode=ParseMode.HTML
        )
        LOGGER.info(f"User {user_id} tried to use /short in group chat")
        return
    
    LOGGER.info(f"User {user_id} started /short command")
    
    try:
        args = get_args(message)
        
        if args and is_valid_url(args[0]):
            long_url = args[0].strip()
            loading = await send_message(
                chat_id=message.chat.id,
                text="<b>Creating Short URL...🔄</b>",
                parse_mode=ParseMode.HTML
            )
            
            async with aiohttp.ClientSession() as session:
                data = await create_short_url(session, long_url)
                
                if data and "short_url" in data:
                    short_url = data["short_url"]
                    original_url = data["original_url"]
                    short_code = data["short_code"]
                    
                    await bot.edit_message_text(
                        text=get_result_message(short_url, original_url),
                        chat_id=message.chat.id,
                        message_id=loading.message_id,
                        reply_markup=build_result_keyboard(short_url),
                        parse_mode=ParseMode.HTML
                    )
                    
                    set_data(user_id, {
                        "short_url": short_url,
                        "original_url": original_url,
                        "short_code": short_code
                    })
                    set_state(user_id, "url_created")
                    LOGGER.info(f"Successfully created short URL for user {user_id}")
                else:
                    await bot.edit_message_text(
                        text="<b>❌ Failed to shorten URL. Try again.</b>",
                        chat_id=message.chat.id,
                        message_id=loading.message_id,
                        parse_mode=ParseMode.HTML
                    )
                    LOGGER.warning(f"Failed to create short URL for user {user_id}")
        else:
            await send_message(
                chat_id=message.chat.id,
                text=get_welcome_message(),
                reply_markup=build_cancel_keyboard(),
                parse_mode=ParseMode.HTML
            )
            set_state(user_id, "waiting_url")
            LOGGER.info(f"Waiting for URL from user {user_id}")
            
    except Exception as e:
        await Smart_Notify(bot, "short_handler", e, message)
        LOGGER.error(f"Failed to start short handler for user {user_id}: {e}")
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Failed to start URL shortener!</b>",
            parse_mode=ParseMode.HTML
        )

@dp.message(lambda m: get_state(m.from_user.id) == "waiting_url" and m.text and m.chat.type == ChatType.PRIVATE)
@new_task
@SmartDefender
async def handle_url_input(message: Message, bot: Bot):
    user_id = message.from_user.id
    url = message.text.strip()
    
    LOGGER.info(f"User {user_id} sent URL: {url[:50]}...")
    
    if not is_valid_url(url):
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Please send a valid HTTP/HTTPS URL.</b>",
            parse_mode=ParseMode.HTML
        )
        LOGGER.warning(f"Invalid URL from user {user_id}")
        return
    
    try:
        await send_message(
            chat_id=message.chat.id,
            text=get_customize_message(),
            reply_markup=build_method_keyboard(),
            parse_mode=ParseMode.HTML
        )
        
        set_data(user_id, {"long_url": url})
        set_state(user_id, "choosing_method")
        LOGGER.info(f"User {user_id} choosing method")
        
    except Exception as e:
        await Smart_Notify(bot, "handle_url_input", e, message)
        LOGGER.error(f"Failed to handle URL input for user {user_id}: {e}")

@dp.message(lambda m: get_state(m.from_user.id) == "entering_custom_slug" and m.text and m.chat.type == ChatType.PRIVATE)
@new_task
@SmartDefender
async def handle_custom_slug(message: Message, bot: Bot):
    user_id = message.from_user.id
    slug = message.text.strip()
    
    LOGGER.info(f"User {user_id} entered custom slug: {slug}")
    
    if not is_valid_slug(slug):
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Invalid slug. Use only letters, numbers, and hyphens.</b>",
            parse_mode=ParseMode.HTML
        )
        LOGGER.warning(f"Invalid slug from user {user_id}")
        return
    
    data = get_data(user_id)
    long_url = data.get("long_url")
    
    if not long_url:
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Session expired. Use /short to start over.</b>",
            parse_mode=ParseMode.HTML
        )
        clear_state(user_id)
        return
    
    try:
        loading = await send_message(
            chat_id=message.chat.id,
            text="<b>Creating Short URL...🔄</b>",
            parse_mode=ParseMode.HTML
        )
        
        async with aiohttp.ClientSession() as session:
            resp = await create_short_url(session, long_url, slug)
            
            if resp and "short_url" in resp:
                short_url = resp["short_url"]
                original_url = resp["original_url"]
                short_code = resp["short_code"]
                
                await bot.edit_message_text(
                    text=get_result_message(short_url, original_url),
                    chat_id=message.chat.id,
                    message_id=loading.message_id,
                    reply_markup=build_result_keyboard(short_url),
                    parse_mode=ParseMode.HTML
                )
                
                set_data(user_id, {
                    "short_url": short_url,
                    "original_url": original_url,
                    "short_code": short_code
                })
                set_state(user_id, "url_created")
                
                await delete_messages(message.chat.id, message.message_id)
                LOGGER.info(f"Successfully created custom short URL for user {user_id}")
            else:
                await bot.edit_message_text(
                    text="<b>❌ Failed to create with custom slug. Try another.</b>",
                    chat_id=message.chat.id,
                    message_id=loading.message_id,
                    parse_mode=ParseMode.HTML
                )
                set_state(user_id, "waiting_url")
                LOGGER.warning(f"Failed to create custom URL for user {user_id}")
                
    except Exception as e:
        await Smart_Notify(bot, "handle_custom_slug", e, message)
        LOGGER.error(f"Failed to handle custom slug for user {user_id}: {e}")

@dp.callback_query(lambda c: c.data == "url_cancel")
async def cancel_action(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    LOGGER.info(f"User {user_id} cancelled URL shortening")
    
    try:
        await callback.message.edit_text(
            "<b>❌ URL shortening cancelled.</b>",
            parse_mode=ParseMode.HTML
        )
        clear_state(user_id)
        await callback.answer()
        LOGGER.info(f"Cancelled for user {user_id}")
        
    except Exception as e:
        await Smart_Notify(bot, "cancel_action", e)
        LOGGER.error(f"Failed to cancel for user {user_id}: {e}")
        await callback.answer("❌ Failed to cancel!", show_alert=True)

@dp.callback_query(lambda c: c.data == "url_auto")
async def auto_generate(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    data = get_data(user_id)
    
    if not data or "long_url" not in data:
        await callback.answer("❌ Session expired. Use /short to start over", show_alert=True)
        LOGGER.warning(f"Session expired for user {user_id} in auto_generate")
        return
    
    LOGGER.info(f"User {user_id} chose auto-generate")
    long_url = data["long_url"]
    
    try:
        await callback.message.edit_text(
            "<b>Creating Short URL...🔄</b>",
            parse_mode=ParseMode.HTML
        )
        
        async with aiohttp.ClientSession() as session:
            resp = await create_short_url(session, long_url)
            
            if resp and "short_url" in resp:
                short_url = resp["short_url"]
                original_url = resp["original_url"]
                short_code = resp["short_code"]
                
                await callback.message.edit_text(
                    text=get_result_message(short_url, original_url),
                    reply_markup=build_result_keyboard(short_url),
                    parse_mode=ParseMode.HTML
                )
                
                set_data(user_id, {
                    "short_url": short_url,
                    "original_url": original_url,
                    "short_code": short_code
                })
                set_state(user_id, "url_created")
                LOGGER.info(f"Successfully auto-generated URL for user {user_id}")
            else:
                await callback.message.edit_text(
                    "<b>❌ Failed to create short URL.</b>",
                    parse_mode=ParseMode.HTML
                )
                set_state(user_id, "waiting_url")
                LOGGER.warning(f"Failed to auto-generate URL for user {user_id}")
        
        await callback.answer()
        
    except Exception as e:
        await Smart_Notify(bot, "auto_generate", e)
        LOGGER.error(f"Failed auto-generate for user {user_id}: {e}")
        await callback.answer("❌ Failed to generate URL!", show_alert=True)

@dp.callback_query(lambda c: c.data == "url_custom")
async def custom_slug(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    data = get_data(user_id)
    
    if not data or "long_url" not in data:
        await callback.answer("❌ Session expired. Use /short to start over", show_alert=True)
        LOGGER.warning(f"Session expired for user {user_id} in custom_slug")
        return
    
    LOGGER.info(f"User {user_id} chose custom slug")
    
    try:
        await callback.message.edit_text(
            "<b>✏️ Enter Custom Slug</b>\n\n"
            "Send your desired short code (e.g., <code>mycode123</code>)\n\n"
            "Only letters, numbers, and hyphens allowed.",
            reply_markup=build_cancel_keyboard(),
            parse_mode=ParseMode.HTML
        )
        set_state(user_id, "entering_custom_slug")
        await callback.answer()
        LOGGER.info(f"Waiting for custom slug from user {user_id}")
        
    except Exception as e:
        await Smart_Notify(bot, "custom_slug", e)
        LOGGER.error(f"Failed to show custom slug prompt for user {user_id}: {e}")
        await callback.answer("❌ Failed to process!", show_alert=True)

@dp.callback_query(lambda c: c.data == "url_refresh")
async def refresh_stats(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    data = get_data(user_id)
    
    if not data or "short_code" not in data:
        await callback.answer("❌ No URL data found", show_alert=True)
        LOGGER.warning(f"No URL data for user {user_id} in refresh_stats")
        return
    
    LOGGER.info(f"User {user_id} refreshing stats")
    await callback.answer("🔄 Refreshing Statistics...")
    
    short_code = data["short_code"]
    short_url = data["short_url"]
    original_url = data["original_url"]
    
    try:
        async with aiohttp.ClientSession() as session:
            stats = await check_stats(session, short_code)
            
            if stats:
                clicks = stats.get("clicks", 0)
                created = stats.get("created_at", "").split()[0] if stats.get("created_at") else datetime.now().strftime("%Y-%m-%d")
                
                await callback.message.edit_text(
                    text=get_result_message(short_url, original_url, clicks, created),
                    reply_markup=build_result_keyboard(short_url),
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Refreshed stats for user {user_id}: {clicks} clicks")
            else:
                await callback.answer("Failed to fetch stats.", show_alert=True)
                LOGGER.warning(f"Failed to fetch stats for user {user_id}")
                
    except Exception as e:
        await Smart_Notify(bot, "refresh_stats", e)
        LOGGER.error(f"Failed to refresh stats for user {user_id}: {e}")
        await callback.answer("❌ Failed to refresh!", show_alert=True)

@dp.callback_query(lambda c: c.data == "url_delete")
async def confirm_delete(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    data = get_data(user_id)
    
    if not data or "short_url" not in data:
        await callback.answer("❌ No URL data found", show_alert=True)
        LOGGER.warning(f"No URL data for user {user_id} in confirm_delete")
        return
    
    LOGGER.info(f"User {user_id} requested delete confirmation")
    short_url = data["short_url"]
    
    try:
        await callback.message.edit_text(
            get_confirm_delete_message(short_url),
            reply_markup=build_confirm_delete_keyboard(),
            parse_mode=ParseMode.HTML
        )
        await callback.answer()
        
    except Exception as e:
        await Smart_Notify(bot, "confirm_delete", e)
        LOGGER.error(f"Failed to show delete confirmation for user {user_id}: {e}")
        await callback.answer("❌ Failed to process!", show_alert=True)

@dp.callback_query(lambda c: c.data == "url_cancel_delete")
async def cancel_delete_action(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    data = get_data(user_id)
    
    if not data or "short_url" not in data:
        await callback.answer("❌ No URL data found", show_alert=True)
        LOGGER.warning(f"No URL data for user {user_id} in cancel_delete_action")
        return
    
    LOGGER.info(f"User {user_id} cancelled delete")
    short_url = data["short_url"]
    original_url = data["original_url"]
    
    try:
        await callback.message.edit_text(
            text=get_result_message(short_url, original_url),
            reply_markup=build_result_keyboard(short_url),
            parse_mode=ParseMode.HTML
        )
        await callback.answer("Delete cancelled")
        
    except Exception as e:
        await Smart_Notify(bot, "cancel_delete_action", e)
        LOGGER.error(f"Failed to cancel delete for user {user_id}: {e}")
        await callback.answer("❌ Failed to cancel!", show_alert=True)

@dp.callback_query(lambda c: c.data == "url_confirm_delete")
async def perform_delete(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    data = get_data(user_id)
    
    if not data or "short_code" not in data:
        await callback.answer("❌ No URL data found", show_alert=True)
        LOGGER.warning(f"No URL data for user {user_id} in perform_delete")
        return
    
    LOGGER.info(f"User {user_id} confirming delete")
    short_code = data["short_code"]
    short_url = data["short_url"]
    
    try:
        await callback.message.edit_text(
            "<b>🗑️ Deleting URL...</b>",
            parse_mode=ParseMode.HTML
        )
        
        async with aiohttp.ClientSession() as session:
            result = await delete_url(session, short_code)
            
            if result and result.get("success"):
                await callback.message.edit_text(
                    get_deleted_message(short_url),
                    parse_mode=ParseMode.HTML
                )
                clear_state(user_id)
                LOGGER.info(f"Successfully deleted URL for user {user_id}")
            else:
                await callback.message.edit_text(
                    "<b>❌ Failed to delete short URL.</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.warning(f"Failed to delete URL for user {user_id}")
        
        await callback.answer()
        
    except Exception as e:
        await Smart_Notify(bot, "perform_delete", e)
        LOGGER.error(f"Failed to delete URL for user {user_id}: {e}")
        await callback.answer("❌ Failed to delete!", show_alert=True)