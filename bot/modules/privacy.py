from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ParseMode
from bot import dp
from bot.helpers.buttons import SmartButtons
from bot.helpers.botutils import send_message
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER

privacy_text = (
    "<b>📜 Privacy Policy for Smart Util Bot</b>\n\n"
    "Welcome to <b>Smart Util Bot</b>. By using our services, you agree to this privacy policy.\n\n"
    "1. <b>Information We Collect:</b>\n"
    "   - <b>Personal Information:</b> User ID and username for personalization.\n"
    "   - <b>Usage Data:</b> Information on how you use the app to improve our services.\n\n"
    "2. <b>Usage of Information:</b>\n"
    "   - <b>Service Enhancement:</b> To provide and improve Smart Util.\n"
    "   - <b>Communication:</b> Updates and new features.\n"
    "   - <b>Security:</b> To prevent unauthorized access.\n"
    "   - <b>Advertisements:</b> Display of promotions.\n\n"
    "3. <b>Data Security:</b>\n"
    "   - These tools do not store any data, ensuring your privacy.\n"
    "   - We use strong security measures, although no system is 100% secure.\n\n"
    "Thank you for using <b>Smart Util Bot</b>. We prioritize your privacy and security."
)

@dp.message(Command(commands=["privacy"], prefix=BotCommands))
async def privacy_command(message: Message, bot: Bot):
    LOGGER.info(f"Received command: '{message.text}' from user {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
    buttons = SmartButtons()
    buttons.button(text="Close ❌", callback_data="close_privacy")
    reply_markup = buttons.build_menu(b_cols=1, h_cols=1, f_cols=1)
    try:
        await send_message(
            chat_id=message.chat.id,
            text=privacy_text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        LOGGER.info(f"Successfully sent privacy message to chat {message.chat.id}")
    except Exception as e:
        LOGGER.error(f"Failed to send privacy message to chat {message.chat.id}: {e}")

@dp.callback_query(lambda c: c.data == "close_privacy")
async def handle_close_privacy_callback(callback_query: CallbackQuery, bot: Bot):
    try:
        await callback_query.message.delete()
        LOGGER.info(f"Successfully deleted privacy message for user {callback_query.from_user.id} in chat {callback_query.message.chat.id}")
    except Exception as e:
        LOGGER.error(f"Failed to delete privacy message for user {callback_query.from_user.id} in chat {callback_query.message.chat.id}: {e}")