import aiohttp
import time
from aiogram import Bot
from aiogram.filters import Command, BaseFilter
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from bot import dp
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.buttons import SmartButtons
from config import A360APIBASEURL

pagination_sessions = {}

class CouponCallbackFilter(BaseFilter):
    async def __call__(self, callback_query: CallbackQuery):
        return callback_query.data.startswith(("cpn_next_", "cpn_prev_"))

@dp.message(Command(commands=["cpn", "promo"], prefix=BotCommands))
@new_task
async def cpn_handler(message: Message, bot: Bot):
    user_id = message.from_user.id if message.from_user else 'Unknown'
    chat_id = message.chat.id
    LOGGER.info(f"Received /cpn command from user: {user_id}")
    loading_message = None
    try:
        args = get_args(message)
        if not args:
            loading_message = await send_message(
                chat_id=chat_id,
                text="<b>❌ Missing store name! Try like this: /cpn amazon</b>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            LOGGER.warning(f"Missing site name from user: {user_id}")
            return

        sitename = args[0].strip().lower()
        sitename_with_com = f"{sitename}.com"
        LOGGER.info(f"Processing site: {sitename_with_com} for user: {user_id}")

        loading_message = await send_message(
            chat_id=chat_id,
            text=f"<b>🔍 Searching Coupon For {sitename}</b>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )

        async with aiohttp.ClientSession() as session:
            async with session.get(f"{A360APIBASEURL}/cpn?site={sitename_with_com}") as resp:
                if resp.status != 200:
                    raise Exception(f"API Error: Status {resp.status}")
                data = await resp.json()
                LOGGER.info(f"API response received for {sitename_with_com}")

        if "results" not in data or not data["results"]:
            await loading_message.edit_text(
                text="<b>❌ No promo code found. Store name is incorrect?</b>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            LOGGER.warning(f"No results found for {sitename_with_com}")
            return

        coupons = data["results"]
        pages = [coupons[i:i + 5] for i in range(0, len(coupons), 5)]
        session_id = f"{chat_id}_{message.message_id}"
        pagination_sessions[session_id] = {
            "coupons": coupons,
            "current_page": 0,
            "timestamp": time.time(),
            "sitename": sitename
        }

        LOGGER.info(f"Parsed {len(coupons)} coupons for {sitename}")

        async def format_page(page_idx):
            start_index = page_idx * 5
            text = f"<b>Successfully Found {len(coupons)} Coupons For {sitename.upper()} ✅</b>\n\n"
            for i, item in enumerate(pages[page_idx], start=start_index + 1):
                title = item.get("title", "No title available")
                code = item.get("code", "No code available")
                text += f"<b>{i}.</b>\n<b>⊗ Title:</b> {title}\n<b>⊗ Coupon Code:</b> <code>{code}</code>\n\n"
            return text.strip()

        buttons = SmartButtons()
        if len(pages) > 1:
            buttons.button(text="➡️ Next", callback_data=f"cpn_next_{session_id}")

        try:
            await loading_message.edit_text(
                text=await format_page(0),
                parse_mode=ParseMode.HTML,
                reply_markup=buttons.build_menu(b_cols=2) if buttons._button else None,
                disable_web_page_preview=True
            )
        except TelegramBadRequest as e:
            LOGGER.warning(f"Failed to apply reply markup: {e}")
            await loading_message.edit_text(
                text=await format_page(0),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )

        LOGGER.info(f"First page sent to user {user_id}")

    except Exception as e:
        LOGGER.error(f"API connection error for {sitename_with_com}: {e}")
        await Smart_Notify(bot, "/cpn", e, message)
        error_text = "<b>❌ Site unreachable or error occurred. Try again later.</b>"
        if loading_message:
            try:
                await loading_message.edit_text(
                    text=error_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
                LOGGER.info(f"Edited loading message with error in chat {chat_id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit loading message in chat {chat_id}: {str(edit_e)}")
                await Smart_Notify(bot, "/cpn", edit_e, message)
                await send_message(
                    chat_id=chat_id,
                    text=error_text,
                    parse_mode=ParseMode.HTML
                )
        else:
            await send_message(
                chat_id=chat_id,
                text=error_text,
                parse_mode=ParseMode.HTML
            )
        LOGGER.info(f"Sent error message to chat {chat_id}")

@dp.callback_query(CouponCallbackFilter())
@new_task
async def handle_pagination(callback_query: CallbackQuery, bot: Bot):
    user_id = callback_query.from_user.id if callback_query.from_user else 'Unknown'
    chat_id = callback_query.message.chat.id
    action, session_id = callback_query.data.split("_", 2)[1:]
    LOGGER.info(f"Pagination '{action}' triggered by user: {user_id}")

    session = pagination_sessions.get(session_id)
    if not session or time.time() - session["timestamp"] > 20:
        LOGGER.warning(f"Session expired for user: {user_id}")
        await callback_query.answer("❌ Session Expired. Try Again.", show_alert=True)
        if session_id in pagination_sessions:
            del pagination_sessions[session_id]
        return

    try:
        coupons = session["coupons"]
        sitename = session["sitename"]
        pages = [coupons[i:i + 5] for i in range(0, len(coupons), 5)]
        page = session["current_page"]

        if action == "next" and page < len(pages) - 1:
            session["current_page"] += 1
        elif action == "prev" and page > 0:
            session["current_page"] -= 1

        page = session["current_page"]
        session["timestamp"] = time.time()

        async def format_page(page_idx):
            start_index = page_idx * 5
            text = f"<b>Successfully Found {len(coupons)} Coupons For {sitename.upper()} ✅</b>\n\n"
            for i, item in enumerate(pages[page_idx], start=start_index + 1):
                title = item.get("title", "No title available")
                code = item.get("code", "No code available")
                text += f"<b>{i}.</b>\n<b>⊗ Title:</b> {title}\n<b>⊗ Coupon Code:</b> <code>{code}</code>\n\n"
            return text.strip()

        buttons = SmartButtons()
        if page > 0:
            buttons.button(text="⬅️ Previous", callback_data=f"cpn_prev_{session_id}")
        if page < len(pages) - 1:
            buttons.button(text="➡️ Next", callback_data=f"cpn_next_{session_id}")

        try:
            await callback_query.message.edit_text(
                text=await format_page(page),
                parse_mode=ParseMode.HTML,
                reply_markup=buttons.build_menu(b_cols=2) if buttons._button else None,
                disable_web_page_preview=True
            )
        except TelegramBadRequest as e:
            LOGGER.warning(f"Failed to edit with reply markup: {e}")
            await callback_query.message.edit_text(
                text=await format_page(page),
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )

        await callback_query.answer()

    except Exception as e:
        LOGGER.error(f"Pagination error for user {user_id}: {e}")
        await Smart_Notify(bot, "/cpn-pagination", e, callback_query.message)
        await callback_query.answer("❌ Something went wrong!", show_alert=True)