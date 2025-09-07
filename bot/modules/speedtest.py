# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
#  Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
import asyncio
import subprocess
import json
from concurrent.futures import ThreadPoolExecutor
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from pyrogram.enums import ParseMode as SmartParseMode
from bot import dp, SmartPyro
from bot.helpers.botutils import send_message, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.buttons import SmartButtons
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.guard import admin_only
from config import UPDATE_CHANNEL_URL

def speed_convert(size: float, is_mbps: bool = False) -> str:
    if is_mbps:
        return f"{size:.2f} Mbps"
    power = 2**10
    n = 0
    power_labels = {0: '', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}bps"

def get_readable_file_size(size_in_bytes: int) -> str:
    if size_in_bytes < 1024:
        return f"{size_in_bytes} B"
    power = 1024
    n = 0
    power_labels = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    while size_in_bytes >= power:
        size_in_bytes /= power
        n += 1
    return f"{size_in_bytes:.2f} {power_labels[n]}"

def run_speedtest():
    try:
        result = subprocess.run(["speedtest-cli", "--secure", "--json"], capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception("Speedtest failed.")
        data = json.loads(result.stdout)
        return data
    except Exception as e:
        LOGGER.error(f"Speedtest error: {e}")
        return {"error": str(e)}

def validate_message(func):
    async def wrapper(message: Message, bot: Bot):
        if not message or not message.from_user:
            LOGGER.error("Invalid message received")
            return
        return await func(message, bot)
    return wrapper

async def run_speedtest_task(bot: Bot, chat_id: int, status_message_id: int):
    with ThreadPoolExecutor() as pool:
        try:
            result = await asyncio.get_running_loop().run_in_executor(pool, run_speedtest)
        except Exception as e:
            LOGGER.error(f"Error running speedtest task: {e}")
            try:
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=status_message_id,
                    text="<b>Speed Test API Dead ❌ </b>",
                    parse_mode=SmartParseMode.HTML
                )
            except Exception as edit_error:
                await Smart_Notify(bot, "run_speedtest_task", edit_error)
                LOGGER.error(f"Failed to edit speedtest message: {edit_error}")
            return

    if "error" in result:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=status_message_id,
                text="<b>Speed Test Failed ❌ </b>",
                parse_mode=SmartParseMode.HTML
            )
        except Exception as edit_error:
            await Smart_Notify(bot, "run_speedtest_task", edit_error)
            LOGGER.error(f"Failed to edit speedtest failed message: {edit_error}")
        return

    response_text = (
        "<b>Smart Speedtest Check → Successful ✅</b>\n"
        "<b>━━━━━━━━━━━━━━━━━</b>\n"
        f"<b>⊗ Download:</b> <b>{speed_convert(result['download'])}</b>\n"
        f"<b>⊗ Upload:</b> <b>{speed_convert(result['upload'])}</b>\n"
        f"<b>⊗ Ping:</b> <b>{result['ping']:.2f} ms</b>\n"
        f"<b>⊗ Internet Provider:</b> <b>{result['client']['isp']}</b>\n"
        "<b>━━━━━━━━━━━━━━━━━</b>\n"
        "<b>Smart SpeedTester → Activated ✅</b>"
    )

    buttons = SmartButtons()
    buttons.button(text="More Info", url=UPDATE_CHANNEL_URL)
    reply_markup = buttons.build_menu(b_cols=1)

    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=status_message_id,
            text=response_text,
            parse_mode=SmartParseMode.HTML,
            reply_markup=reply_markup
        )
    except Exception as edit_error:
        await Smart_Notify(bot, "run_speedtest_task", edit_error)
        LOGGER.error(f"Failed to edit speedtest result message: {edit_error}")

@dp.message(Command(commands=["speedtest"], prefix=BotCommands))
@validate_message
@admin_only
async def speedtest_handler(message: Message, bot: Bot):
    try:
        status_message = await send_message(
            chat_id=message.chat.id,
            text="<b>Processing SpeedTest Please Wait....</b>",
            parse_mode=SmartParseMode.HTML
        )

        if status_message:
            asyncio.create_task(run_speedtest_task(bot, message.chat.id, status_message.message_id))
            LOGGER.info(f"Speedtest command initiated by user_id {message.from_user.id}")
        else:
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Failed to start speedtest!</b>",
                parse_mode=SmartParseMode.HTML
            )
            LOGGER.error(f"Failed to send initial speedtest message for user_id {message.from_user.id}")

    except Exception as e:
        await Smart_Notify(bot, "speedtest_handler", e, message)
        LOGGER.error(f"Failed to handle speedtest command for user_id {message.from_user.id}: {e}")
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Failed to initiate speedtest!</b>",
            parse_mode=SmartParseMode.HTML
        )