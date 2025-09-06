from aiogram import Bot
from aiogram.types import Message
from bot.core.database import SmartGuards
from bot.helpers.logger import LOGGER
from config import OWNER_ID

def admin_only(func):
    async def wrapper(message: Message, bot: Bot):
        user_id = message.from_user.id
        auth_admins_data = await SmartGuards.find({}, {"user_id": 1, "_id": 0}).to_list(None)
        AUTH_ADMIN_IDS = [admin["user_id"] for admin in auth_admins_data]
        if user_id != OWNER_ID and user_id not in AUTH_ADMIN_IDS:
            LOGGER.info(f"Unauthorized settings access attempt by user_id {user_id}")
            return
        return await func(message, bot)
    return wrapper