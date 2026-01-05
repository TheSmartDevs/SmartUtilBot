import asyncio
import os
import shutil
import subprocess
import sys
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message
from pyrogram.enums import ParseMode as SmartParseMode
from bot import dp, SmartPyro, SmartUserBot
from bot.helpers.botutils import send_message
from bot.helpers.guard import admin_only
from bot.core.database import SmartReboot
from bot.helpers.logger import LOGGER
from bot.helpers.commands import BotCommands
from config import UPDATE_CHANNEL_URL

async def cleanup_restart_data():
    try:
        await SmartReboot.delete_many({})
        LOGGER.info("Cleaned up existing restart messages from database")
    except Exception as e:
        LOGGER.error(f"Failed to cleanup restart data: {e}")

def validate_message(func):
    async def wrapper(message: Message, bot: Bot):
        if not message or not message.from_user:
            LOGGER.error("Invalid message received")
            return
        return await func(message, bot)
    return wrapper

async def run_restart_task(bot: Bot, chat_id: int, status_message_id: int):
    session_file = "SmartUtilBot.session"
    if os.path.exists(session_file) and not os.access(session_file, os.W_OK):
        try:
            os.chmod(session_file, 0o600)
            LOGGER.info(f"Set write permissions for {session_file}")
        except Exception as e:
            LOGGER.error(f"Failed to set permissions for {session_file}: {e}")
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_message_id,
                text="<b>Failed To Restart: Read-Only Environment</b>",
                parse_mode=SmartParseMode.HTML
            )
            return

    directories = ["downloads", "temp", "temp_media", "data", "repos", "temp_dir"]
    for directory in directories:
        try:
            if os.path.exists(directory):
                shutil.rmtree(directory)
                LOGGER.info(f"Cleared directory: {directory}")
        except Exception as e:
            LOGGER.error(f"Failed to clear directory {directory}: {e}")

    log_file = "botlog.txt"
    if os.path.exists(log_file):
        try:
            os.remove(log_file)
            LOGGER.info(f"Cleared log file: {log_file}")
        except Exception as e:
            LOGGER.error(f"Failed to clear log file {log_file}: {e}")

    start_script = "start.sh"
    module_execution = ["python3", "-m", "bot"]

    try:
        await cleanup_restart_data()
        restart_data = {
            "chat_id": chat_id,
            "msg_id": status_message_id
        }
        await SmartReboot.insert_one(restart_data)
        LOGGER.info(f"Stored restart message details for chat {chat_id}")
        await asyncio.sleep(2)

        try:
            await SmartPyro.stop()
            LOGGER.info("Terminated SmartPyro session")
        except Exception as e:
            LOGGER.error(f"Failed to stop SmartPyro: {e}")

        try:
            await SmartUserBot.stop()
            LOGGER.info("Terminated SmartUserBot session")
        except Exception as e:
            LOGGER.error(f"Failed to stop SmartUserBot: {e}")

        try:
            await bot.session.close()
            LOGGER.info("Terminated SmartAIO session")
        except Exception as e:
            LOGGER.error(f"Failed to close SmartAIO session: {e}")

        if os.path.exists(start_script) and os.access(start_script, os.X_OK):
            process = subprocess.Popen(
                ["bash", start_script],
                stdin=subprocess.DEVNULL,
                stdout=None,
                stderr=None,
                start_new_session=True
            )
            LOGGER.info("Started bot using bash script")
        else:
            process = subprocess.Popen(
                module_execution,
                stdin=subprocess.DEVNULL,
                stdout=None,
                stderr=None,
                start_new_session=True,
                cwd=os.getcwd()
            )
            LOGGER.info("Started bot using python3 -m bot")

        await asyncio.sleep(3)
        if process.poll() is not None and process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, "bot")

        LOGGER.info("Restart executed successfully, shutting down current instance")
        await asyncio.sleep(2)
        os._exit(0)

    except subprocess.CalledProcessError as e:
        LOGGER.error(f"Start process failed with return code {e.returncode}")
        await SmartReboot.delete_one({"chat_id": chat_id, "msg_id": status_message_id})
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_message_id,
            text="<b>Failed To Restart: Invalid Script Execution</b>",
            parse_mode=SmartParseMode.HTML
        )
    except FileNotFoundError:
        LOGGER.error("Python or bash shell not found")
        await SmartReboot.delete_one({"chat_id": chat_id, "msg_id": status_message_id})
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_message_id,
            text="<b>Failed To Restart: System Command Not Found</b>",
            parse_mode=SmartParseMode.HTML
        )
    except Exception as e:
        LOGGER.error(f"Restart command execution failed: {e}")
        await SmartReboot.delete_one({"chat_id": chat_id, "msg_id": status_message_id})
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_message_id,
            text="<b>Failed To Restart: System Error</b>",
            parse_mode=SmartParseMode.HTML
        )

@dp.message(Command(commands=["restart", "reboot", "reload"], prefix=BotCommands))
@validate_message
@admin_only
async def restart_handler(message: Message, bot: Bot):
    try:
        status_message = await send_message(
            chat_id=message.chat.id,
            text="<b>Restarting Bot... Please Wait.</b>",
            parse_mode=SmartParseMode.HTML
        )
        if status_message:
            asyncio.create_task(run_restart_task(bot, message.chat.id, status_message.message_id))
            LOGGER.info(f"Restart command initiated by user_id {message.from_user.id}")
        else:
            await send_message(
                chat_id=message.chat.id,
                text="<b>Failed to start restart!</b>",
                parse_mode=SmartParseMode.HTML
            )
            LOGGER.error(f"Failed to send initial restart message for user_id {message.from_user.id}")
    except Exception as e:
        LOGGER.error(f"Failed to handle restart command for user_id {message.from_user.id}: {e}")
        await send_message(
            chat_id=message.chat.id,
            text="<b>Failed to initiate restart!</b>",
            parse_mode=SmartParseMode.HTML
        )

@dp.message(Command(commands=["stop", "kill", "off"], prefix=BotCommands))
@validate_message
@admin_only
async def stop_handler(message: Message, bot: Bot):
    try:
        status_message = await send_message(
            chat_id=message.chat.id,
            text="<b>Stopping bot and clearing data...</b>",
            parse_mode=SmartParseMode.HTML
        )
        directories = ["downloads"]
        for directory in directories:
            try:
                if os.path.exists(directory):
                    shutil.rmtree(directory)
                    LOGGER.info(f"Cleared directory: {directory}")
            except Exception as e:
                LOGGER.error(f"Failed to clear directory {directory}: {e}")

        log_file = "botlog.txt"
        if os.path.exists(log_file):
            try:
                os.remove(log_file)
                LOGGER.info(f"Cleared log file: {log_file}")
            except Exception as e:
                LOGGER.error(f"Failed to clear log file {log_file}: {e}")

        await cleanup_restart_data()

        try:
            await SmartPyro.stop()
            LOGGER.info("Terminated SmartPyro session")
        except Exception as e:
            LOGGER.error(f"Failed to stop SmartPyro: {e}")

        try:
            await SmartUserBot.stop()
            LOGGER.info("Terminated SmartUserBot session")
        except Exception as e:
            LOGGER.error(f"Failed to stop SmartUserBot: {e}")

        try:
            await bot.session.close()
            LOGGER.info("Terminated SmartAIO session")
        except Exception as e:
            LOGGER.error(f"Failed to close SmartAIO session: {e}")

        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=status_message.message_id,
            text="<b>Bot stopped successfully, data cleared</b>",
            parse_mode=SmartParseMode.HTML
        )
        await asyncio.sleep(2)
        try:
            subprocess.run(["pkill", "-f", "python3 -m bot"], check=False, timeout=5)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            LOGGER.warning("pkill command failed or timed out, using direct exit")
        os._exit(0)
    except Exception as e:
        LOGGER.error(f"Failed to handle stop command: {e}")
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=status_message.message_id,
            text="<b>Failed To Stop Bot: System Error</b>",
            parse_mode=SmartParseMode.HTML
        )
        await asyncio.sleep(2)
        os._exit(0)