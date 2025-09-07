# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
#  Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
import asyncio
import logging
import os
from bot import SmartAIO, dp, SmartPyro, SmartUserBot
from bot.core.database import SmartReboot
from bot.helpers.logger import LOGGER
from bot.misc.callback import handle_callback_query
from importlib import import_module

async def main():
    try:
        restart_data = await SmartReboot.find_one()
        if restart_data:
            try:
                await SmartAIO.edit_message_text(
                    chat_id=restart_data["chat_id"],
                    message_id=restart_data["msg_id"],
                    text="<b>Restarted Successfully 💥</b>",
                    parse_mode="HTML"
                )
                await SmartReboot.delete_one({"_id": restart_data["_id"]})
                LOGGER.info(f"Restart message updated and cleared from database for chat {restart_data['chat_id']}")
            except Exception as e:
                LOGGER.error(f"Failed to update restart message: {e}")

        modules_path = "bot.modules"
        modules_dir = os.path.join(os.path.dirname(__file__), "modules")
        for filename in os.listdir(modules_dir):
            if filename.endswith(".py") and filename != "__init__.py":
                module_name = filename[:-3]
                import_module(f"{modules_path}.{module_name}")

        dp.callback_query.register(handle_callback_query)

        await SmartPyro.start()
        await SmartUserBot.start()
        LOGGER.info("Bot Successfully Started 💥")
        await dp.start_polling(SmartAIO, drop_pending_updates=True)
    except asyncio.CancelledError:
        LOGGER.info("Polling cancelled, shutting down...")
        raise

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        LOGGER.info("Stop signal received. Shutting down...")
        try:
            stop_tasks = []
            if SmartAIO.session.is_connected:
                stop_tasks.append(SmartAIO.session.stop())
            if SmartPyro.is_connected:
                stop_tasks.append(SmartPyro.stop())
            if SmartUserBot.is_connected:
                stop_tasks.append(SmartUserBot.stop())
            if stop_tasks:
                loop.run_until_complete(asyncio.gather(*stop_tasks))
        except Exception as e:
            LOGGER.error(f"Failed to stop clients: {e}")
        finally:
            if not loop.is_closed():
                loop.close()
