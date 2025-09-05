import aiohttp
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode, ChatType
from bot import dp, SmartAIO
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages
from bot.helpers.notify import Smart_Notify
from bot.helpers.logger import LOGGER
from bot.helpers.buttons import SmartButtons
from bot.helpers.commands import BotCommands
from config import A360APIBASEURL

logger = LOGGER

@dp.message(Command(commands=["ytag"], prefix=BotCommands))
@new_task
async def ytag(message: Message, bot: Bot):
    if message.chat.type not in [ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP]:
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ This command only works in private or group chats</b>",
            parse_mode=ParseMode.HTML
        )
        return
    logger.info(f"Command received from user {message.from_user.id} in chat {message.chat.id}: {message.text}")
    if len(message.text.split()) < 2:
        logger.warning("No URL provided")
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Please provide a YouTube URL. Usage: /ytag [URL]</b>",
            parse_mode=ParseMode.HTML
        )
        return
    url = message.text.split()[1].strip()
    logger.debug(f"Processing URL: {url}")
    fetching_msg = await send_message(
        chat_id=message.chat.id,
        text="<b>Processing Your Request...</b>",
        parse_mode=ParseMode.HTML
    )
    logger.debug(f"Sent fetching message {fetching_msg.message_id}")
    try:
        api_url = f"{A360APIBASEURL}/yt/dl?url={url}"
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as resp:
                if resp.status != 200:
                    raise Exception(f"API returned status {resp.status}")
                data = await resp.json()
        tags = data.get("tags", [])
        if not tags:
            response = "<b>Sorry, no tags available for this video.</b>"
        else:
            tags_str = "\n".join([f"<code>{tag}</code>" for tag in tags])
            response = f"<b>Your Requested Video Tags ✅</b>\n<b>━━━━━━━━━━━━━━━━</b>\n{tags_str}"
        await SmartAIO.edit_message_text(
            chat_id=message.chat.id,
            message_id=fetching_msg.message_id,
            text=response,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        logger.info(f"Sent tags for {url}")
    except Exception as e:
        logger.error(f"Error extracting YouTube tags for URL {url}: {e}")
        await SmartAIO.edit_message_text(
            chat_id=message.chat.id,
            message_id=fetching_msg.message_id,
            text="<b>Sorry Bro YouTube Tags API Dead</b>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )
        await Smart_Notify(bot, "/ytag", e, message)