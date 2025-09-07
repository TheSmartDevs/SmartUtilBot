# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
#  Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
import asyncio
import os
import shutil
import subprocess
import sys
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message
from pyrogram.enums import ParseMode as SmartParseMode
from bot import dp, SmartPyro
from bot.helpers.botutils import send_message
from bot.helpers.guard import admin_only
from bot.core.database import SmartReboot
from bot.helpers.logger import LOGGER
from config import UPDATE_CHANNEL_URL

async def cleanup_restart_data():
    try:
        await SmartReboot.delete_many({})
        LOGGER.info("Cleaned up any existing restart messages from database")
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
    if not os.access(session_file, os.W_OK) if os.path.exists(session_file) else True:
        try:
            os.chmod(session_file, 0o600)
            LOGGER.info(f"Set write permissions for {session_file}")
        except Exception as e:
            LOGGER.error(f"Failed to set permissions for {session_file}: {e}")
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_message_id,
                text="<b>Failed To Restart Due To ReadOnly Environment</b>",
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
    main_script = "main.py"

    if not os.path.exists(start_script):
        if not os.path.exists(main_script):
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_message_id,
                text="<b>Failed To Restart Due To Missing Scripts</b>",
                parse_mode=SmartParseMode.HTML
            )
            LOGGER.error("Neither start.sh nor main.py found")
            return
        start_script = None

    try:
        await cleanup_restart_data()
        restart_data = {
            "chat_id": chat_id,
            "msg_id": status_message_id
        }
        await SmartReboot.insert_one(restart_data)
        LOGGER.info(f"Stored restart message details for chat {chat_id}")
        await asyncio.sleep(2)

        if start_script:
            if not os.access(start_script, os.X_OK):
                os.chmod(start_script, 0o755)
                LOGGER.info(f"Set execute permissions for {start_script}")
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
                [sys.executable, main_script],
                stdin=subprocess.DEVNULL,
                stdout=None,
                stderr=None,
                start_new_session=True,
                cwd=os.getcwd()
            )
            LOGGER.info("Started bot using direct python execution")

        await asyncio.sleep(3)
        if process.poll() is not None and process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, start_script or main_script)

        LOGGER.info("Restart executed successfully, shutting down current instance")
        await asyncio.sleep(2)
        os._exit(0)

    except subprocess.CalledProcessError as e:
        LOGGER.error(f"Start process failed with return code {e.returncode}")
        await SmartReboot.delete_one({"chat_id": chat_id, "msg_id": status_message_id})
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_message_id,
            text="<b>Failed To Restart Invalid Script Format</b>",
            parse_mode=SmartParseMode.HTML
        )
    except FileNotFoundError:
        LOGGER.error("Bash shell or script not found")
        await SmartReboot.delete_one({"chat_id": chat_id, "msg_id": status_message_id})
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_message_id,
            text="<b>Failed To Restart Due To Unix Issue</b>",
            parse_mode=SmartParseMode.HTML
        )
    except Exception as e:
        LOGGER.error(f"Restart command execution failed: {e}")
        await SmartReboot.delete_one({"chat_id": chat_id, "msg_id": status_message_id})
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_message_id,
            text="<b>Failed To Restart Due To System Error</b>",
            parse_mode=SmartParseMode.HTML
        )

@dp.message(Command(commands=["restart", "reboot", "reload"]))
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

@dp.message(Command(commands=["stop", "kill", "off"]))
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
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=status_message.message_id,
            text="<b>Bot stopped successfully, data cleared</b>",
            parse_mode=SmartParseMode.HTML
        )
        await asyncio.sleep(2)
        try:
            subprocess.run(["pkill", "-f", "main.py"], check=False, timeout=5)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            LOGGER.warning("pkill command failed or timed out, using direct exit")
        os._exit(0)
    except Exception as e:
        LOGGER.error(f"Failed to handle stop command: {e}")
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=status_message.message_id,
            text="<b>Failed To Stop Bot Due To System Error</b>",
            parse_mode=SmartParseMode.HTML
        )
        await asyncio.sleep(2)
        os._exit(0)