from bot.core.database import check_ban as ban_collection
from bot.helpers import LOGGER

async def check_ban(user_id):
    try:
        if user_id and await ban_collection.find_one({"user_id": user_id}):
            return True
        return False
    except Exception as e:
        LOGGER.error(f"Failed to check ban for user {user_id}: {e}")
        return False