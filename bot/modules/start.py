import asyncio
from bot import dp
from config import UPDATE_CHANNEL_URL
from bot.helpers.botutils import send_message, delete_messages
from bot.helpers.buttons import SmartButtons
from bot.helpers.commands import BotCommands
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from aiogram.enums import ChatType

@dp.message(CommandStart())
@dp.message(Command(commands=["start"], prefix=BotCommands))
async def start_command_handler(message: Message):
    chat_id = message.chat.id

    animation_message = await send_message(
        chat_id=chat_id,
        text="<b>Starting The Smart-Util bot...</b>"
    )
    if not animation_message:
        return

    await asyncio.sleep(0.2)
    await animation_message.edit_text("<b>Getting session keys wait...</b>")
    await asyncio.sleep(0.2)
    await delete_messages(chat_id=chat_id, message_ids=animation_message.message_id)

    buttons = SmartButtons()
    buttons.button(text="⚙️ Main Menu", callback_data="main_menu", position="header")
    buttons.button(text="ℹ️ About Me", callback_data="about_me")
    buttons.button(text="🗒 Policy & Terms", callback_data="policy_terms")
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
                f"<b>Hi{group_name} Welcome To This Bot</b>\n"
                "<b>━━━━━━━━━━━━━━━━━━━━━</b>\n"
                "<b>Smart Util</b> is your ultimate toolkit on Telegram, packed with AI tools, "
                "educational resources, downloaders, temp mail, crypto utilities, and more. "
                "Simplify your tasks with ease!\n"
                "<b>━━━━━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>Don't forget to <a href='{UPDATE_CHANNEL_URL}'>join here</a> for updates!</b>"
            )

    await send_message(
        chat_id=chat_id,
        text=response_text,
        reply_markup=reply_markup,
        disable_web_page_preview=True
    )