# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
#  Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
from aiogram import Bot
from aiogram.types import Message
from .buttons import SmartButtons
from .botutils import send_message
from .logger import LOGGER
from .notify import Smart_Notify
from pyrogram.enums import ParseMode as SmartParseMode
from config import OWNER_ID

async def SmartShield(bot: Bot, chat_id: int, message: Message = None):
    try:
        buttons = SmartButtons()
        buttons.button(text="Contact Owner 👨🏻‍💻", url=f"tg://user?id={OWNER_ID}")
        reply_markup = buttons.build_menu(b_cols=1)
        ban_message = (
            "<b>❌ Sorry Bro You're Banned From Using Me</b>\n"
            "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
            "<b>You're Currently Banned From Using Me Or My Services.\n"
            "If you believe this was a mistake or want to appeal, \n"
            "please contact the admin. 🚨</b>\n"
            "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
            "<b>Note: NSFW Work Can Cause Forever Ban ✅</b>"
        )
        await send_message(
            chat_id=chat_id,
            text=ban_message,
            parse_mode=SmartParseMode.HTML,
            reply_markup=reply_markup
        )
    except Exception as e:
        await Smart_Notify(bot, "SmartShield", e, message)
        LOGGER.error(f"Error sending ban message to {chat_id}: {e}")