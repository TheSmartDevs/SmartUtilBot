# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
#  Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
from aiogram import Bot
from bot import dp
from config import UPDATE_CHANNEL_URL
from bot.helpers.botutils import send_message
from bot.helpers.buttons import SmartButtons
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.utils import new_task
from bot.helpers.defend import SmartDefender
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ChatType

@dp.message(Command(commands=["help", "cmds"], prefix=BotCommands))
@new_task
@SmartDefender
async def help_command_handler(message: Message, bot: Bot):
    LOGGER.info(f"Received command: '{message.text}' from user {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
    chat_id = message.chat.id

    buttons = SmartButtons()
    buttons.button(text="⚙️ Main Menu", callback_data="main_menu", position="header")
    buttons.button(text="ℹ️ About Me", callback_data="about_me")
    buttons.button(text="📄 Policy & Terms", callback_data="policy_terms")
    reply_markup = buttons.build_menu(b_cols=2, h_cols=1, f_cols=1)

    if message.chat.type == ChatType.PRIVATE:
        full_name = "User"
        if message.from_user:
            full_name = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip()

        response_text = (
            f"<b>Hi {full_name}! Welcome To This Bot</b>\n"
            "<b>━━━━━━━━━━━━━━━━━━━━━</b>\n"
            "<b>Smart Util</b> is your ultimate toolkit on Telegram, packed with AI tools, "
            "educational resources, downloaders, temp mail, crypto utilities, and more. "
            "Simplify your tasks with ease!\n"
            "<b>━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>Don't forget to <a href='{UPDATE_CHANNEL_URL}'>join here</a> for updates!</b>"
        )
    else:  
        group_name = message.chat.title or "this group"
        if message.from_user:
            full_name = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip()
            response_text = (
                f"<b>Hi {full_name}! Welcome To This Bot</b>\n"
                "<b>━━━━━━━━━━━━━━━━━━━━━</b>\n"
                "<b>Smart Util</b> is your ultimate toolkit on Telegram, packed with AI tools, "
                "educational resources, downloaders, temp mail, crypto utilities, and more. "
                "Simplify your tasks with ease!\n"
                "<b>━━━━━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>Don't forget to <a href='{UPDATE_CHANNEL_URL}'>join here</a> for updates!</b>"
            )
        else:  
            response_text = (
                f"<b>Hi {group_name} Welcome To This Bot</b>\n"
                "<b>━━━━━━━━━━━━━━━━━━━━━</b>\n"
                "<b>Smart Util</b> is your ultimate toolkit on Telegram, packed with AI tools, "
                "educational resources, downloaders, temp mail, crypto utilities, and more. "
                "Simplify your tasks with ease!\n"
                "<b>━━━━━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>Don't forget to <a href='{UPDATE_CHANNEL_URL}'>join here</a> for updates!</b>"
            )

    try:
        await send_message(
            chat_id=chat_id,
            text=response_text,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
        LOGGER.info(f"Successfully sent help message to chat {chat_id}")
    except Exception as e:
        LOGGER.error(f"Failed to send help message to chat {chat_id}: {e}")
        await Smart_Notify(bot, "help", e, message)
        await send_message(
            chat_id=chat_id,
            text="<b>❌ Sorry, an error occurred while processing the help command</b>",
            parse_mode=ParseMode.HTML
        )
        LOGGER.info(f"Sent error message to chat {chat_id}")