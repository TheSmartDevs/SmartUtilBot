from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.enums import ParseMode, ChatType
from bot import dp
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from config import A360APIBASEURL
import aiohttp
import aiofiles
import json
from typing import Optional

@dp.message(Command(commands=["getusers"], prefix=BotCommands))
@new_task
async def get_users(message: Message, bot: Bot) -> None:
    user_id = message.from_user.id
    chat_id = message.chat.id
    LOGGER.info(f"User {user_id} initiated /getusers command in chat {chat_id}")

    if message.chat.type != ChatType.PRIVATE:
        LOGGER.info(f"User {user_id} attempted /getusers in non-private chat {chat_id}")
        await send_message(
            chat_id=chat_id,
            text="<b>❌ This command is only available in private chats.</b>",
            parse_mode=ParseMode.HTML
        )
        return

    args = get_args(message)
    if not args:
        LOGGER.error(f"User {user_id} provided no bot token")
        await send_message(
            chat_id=chat_id,
            text="<b>❌ Please provide a valid bot token after the command.</b>",
            parse_mode=ParseMode.HTML
        )
        return

    bot_token = args[0].strip()
    loading_message = await send_message(
        chat_id=chat_id,
        text="<b>Fetching user data...</b>",
        parse_mode=ParseMode.HTML
    )

    LOGGER.info(f"Validating bot token ending in {bot_token[-4:]}")
    bot_info = await validate_bot_token(bot_token)
    if bot_info is None:
        LOGGER.error(f"Invalid bot token provided by user {user_id}")
        await loading_message.edit_text(
            text="<b>❌ Invalid Bot Token Provided</b>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        return

    LOGGER.info(f"Fetching data for bot {bot_info.get('username', 'N/A')}")
    data = await fetch_bot_data(bot_token)
    if data is None:
        LOGGER.error(f"Failed to fetch user data for user {user_id}")
        await loading_message.edit_text(
            text="<b>❌ Failed to fetch user data</b>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        return

    file_path = f"users_{user_id}.json"
    temp_files = [file_path]
    try:
        await save_and_send_data(bot, chat_id, data, file_path)
        LOGGER.info(f"Successfully sent user data to user {user_id} in chat {chat_id}")
        await delete_messages(chat_id, loading_message.message_id)
    except Exception as e:
        LOGGER.exception(f"Error processing data for user {user_id}: {str(e)}")
        await Smart_Notify(bot, "/getusers", e, message)
        await loading_message.edit_text(
            text="<b>❌ Error processing data</b>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
    finally:
        clean_download(*temp_files)

async def validate_bot_token(bot_token: str) -> Optional[dict]:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.telegram.org/bot{bot_token}/getMe") as resp:
                if resp.status != 200:
                    LOGGER.warning(f"Telegram API returned status {resp.status} for bot token")
                    return None
                data = await resp.json()
                if not data.get("ok", False) or "result" not in data:
                    LOGGER.warning(f"Invalid Telegram API response: {data}")
                    return None
                return data["result"]
    except aiohttp.ClientError as e:
        LOGGER.error(f"Telegram API request failed: {str(e)}")
        return None

async def fetch_bot_data(bot_token: str) -> Optional[dict]:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{A360APIBASEURL}/tgusers?token={bot_token}") as resp:
                if resp.status != 200:
                    LOGGER.warning(f"API returned status {resp.status} for bot token")
                    return None
                data = await resp.json()
                if not isinstance(data, dict) or "bot_info" not in data or "users" not in data or "chats" not in data:
                    LOGGER.error(f"Invalid API response structure for bot token")
                    return None
                return data
    except aiohttp.ClientError as e:
        LOGGER.error(f"API request failed: {str(e)}")
        return None

async def save_and_send_data(bot: Bot, chat_id: int, data: dict, file_path: str) -> None:
    async with aiofiles.open(file_path, mode='w') as f:
        await f.write(json.dumps(data, indent=4))
    LOGGER.debug(f"Saved data to {file_path}")

    bot_info = data.get("bot_info", {})
    total_users = data.get("total_users", 0)
    total_chats = data.get("total_chats", 0)
    
    caption = (
        "<b>📌 Requested Users</b>\n"
        "<b>━━━━━━━━</b>\n"
        f"<b>👤 Username:</b> <code>{bot_info.get('username', 'N/A')}</code>\n"
        f"<b>👥 Total Users:</b> <code>{total_users}</code>\n"
        f"<b>👥 Total Chats:</b> <code>{total_chats}</code>\n"
        "<b>━━━━━━━━</b>\n"
        "<b>📂 File contains user & chat IDs.</b>"
    )

    await bot.send_document(
        chat_id=chat_id,
        document=FSInputFile(file_path),
        caption=caption,
        parse_mode=ParseMode.HTML
    )
    LOGGER.info(f"Sent document to chat {chat_id}")