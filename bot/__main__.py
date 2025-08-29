import asyncio
from bot import SmartGram, SmartUser
from bot.core.database import check_restart
from bot.helpers import LOGGER
from bot.miscs import SmartCallback
from pyrogram import handlers
from pyrogram.enums import ParseMode

async def main():
    await SmartGram.start()
    await SmartUser.start()
    SmartGram.add_handler(handlers.CallbackQueryHandler(SmartCallback))
    LOGGER.info("Bot Successfully Started! 💥")
    try:
        restart_data = await check_restart.find_one()
        if restart_data:
            try:
                await SmartGram.edit_message_text(
                    chat_id=restart_data["chat_id"],
                    message_id=restart_data["msg_id"],
                    text="**Restarted Successfully 💥**",
                    parse_mode=ParseMode.MARKDOWN
                )
                await check_restart.delete_one({"_id": restart_data["_id"]})
                LOGGER.info(f"Restart message updated and cleared from database for chat {restart_data['chat_id']}")
            except Exception as e:
                LOGGER.error(f"Failed to update restart message: {e}")
    except Exception as e:
        LOGGER.error(f"Failed to fetch restart message from database: {e}")
    await asyncio.Event().wait()
    await SmartGram.stop()
    await SmartUser.stop()
    LOGGER.info("Bot Stopped Successfully!")

if __name__ == "__main__":
    asyncio.run(main())