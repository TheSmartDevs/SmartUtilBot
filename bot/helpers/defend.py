# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
#  Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
from aiogram import Bot
from aiogram.types import Message
from .security import SmartShield
from bot.core.database import SmartSecurity
from .logger import LOGGER
from .notify import Smart_Notify

def SmartDefender(func):
    async def wrapper(message: Message, bot: Bot):
        try:
            if await SmartSecurity.find_one({"user_id": message.from_user.id}):
                await SmartShield(bot, message.from_user.id, message)
                return
            return await func(message, bot)
        except Exception as e:
            await Smart_Notify(bot, "SmartDefender", e, message)
            LOGGER.error(f"Error in SmartDefender for user {message.from_user.id}: {e}")
            await SmartShield(bot, message.from_user.id, message)
    return wrapper