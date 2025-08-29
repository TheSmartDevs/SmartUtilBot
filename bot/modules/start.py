from bot import SmartGram
from bot.helpers import LOGGER, check_ban, send_message, delete_messages, SmartButtons, BotCommand
from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup
from pyrogram.enums import ParseMode, ChatType
import asyncio
from ..config import UPDATE_CHANNEL_URL, BAN_REPLY

@SmartGram.on_message(filters.command(["start"], prefixes=BotCommand) & (filters.private | filters.group))
async def start_message(client, message):
    user_id = message.from_user.id if message.from_user else None
    if user_id and await check_ban(user_id):
        await send_message(message.chat.id, BAN_REPLY, parse_mode=ParseMode.MARKDOWN)
        return
    chat_id = message.chat.id
    animation_message = await send_message(chat_id, "<b>Starting Smart Tool ⚙️...</b>", parse_mode=ParseMode.HTML)
    await asyncio.sleep(0.4)
    await send_message(chat_id, "<b>Generating Session Keys Please Wait...</b>", parse_mode=ParseMode.HTML, reply_to_message_id=animation_message.id)
    await asyncio.sleep(0.4)
    await delete_messages(chat_id, animation_message.id)
    if message.chat.type == ChatType.PRIVATE:
        full_name = "User"
        if message.from_user:
            first_name = message.from_user.first_name or ""
            last_name = message.from_user.last_name or ""
            full_name = f"{first_name} {last_name}".strip()
        response_text = (
            f"<b>Hi {full_name}! Welcome To This Bot</b>\n"
            "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>Smart Tool</b> The ultimate toolkit on Telegram, offering education, AI, downloaders, temp mail, credit cards, and more. Simplify your tasks with ease!\n"
            "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>Don't forget to <a href='{UPDATE_CHANNEL_URL}'>Join Here</a> for updates!</b>".format(UPDATE_CHANNEL_URL=UPDATE_CHANNEL_URL)
        )
    elif message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        group_name = message.chat.title if message.chat.title else "this group"
        if message.from_user:
            first_name = message.from_user.first_name or ""
            last_name = message.from_user.last_name or ""
            full_name = f"{first_name} {last_name}".strip()
            response_text = (
                f"<b>Hi {full_name}! Welcome To This Bot</b>\n"
                "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>Smart Tool </b> The ultimate toolkit on Telegram, offering education, AI, downloaders, temp mail, credit cards, and more. Simplify your tasks with ease!\n"
                "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>Don't forget to <a href='{UPDATE_CHANNEL_URL}'>Join Here</a> for updates!</b>".format(UPDATE_CHANNEL_URL=UPDATE_CHANNEL_URL)
            )
        else:
            response_text = (
                f"<b>Hi! Welcome {group_name} To This Bot</b>\n"
                "<b>━━━━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>Smart Tool </b> The ultimate toolkit on Telegram, offering education, AI, downloaders, temp mail, credit cards, and more. Simplify your tasks with ease!\n"
                "<b>━━━━━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>Don't forget to <a href='{UPDATE_CHANNEL_URL}'>Join Here</a> for updates!</b>".format(UPDATE_CHANNEL_URL=UPDATE_CHANNEL_URL)
            )
    buttons = SmartButtons()
    buttons.button("⚙️ Main Menu", callback_data="main_menu")
    buttons.button("ℹ️ About Me", callback_data="about_me")
    buttons.button("📄 Policy & Terms", callback_data="policy_terms")
    await send_message(
        chat_id=message.chat.id,
        text=response_text,
        parse_mode=ParseMode.HTML,
        reply_markup=buttons.build_menu(b_cols=2),
        disable_web_page_preview=True
    )