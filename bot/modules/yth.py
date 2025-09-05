import aiohttp
import re
import os
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
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

def youtube_parser(url):
    reg_exp = r"(?:youtube\.com/(?:[^/]+/.+/|(?:v|e(?:mbed)?)|.*[?&]v=)|youtu\.be/)([^\"&?/ ]{11})"
    try:
        match = re.search(reg_exp, url)
        return match.group(1) if match else False
    except Exception as e:
        logger.error(f"Error parsing YouTube URL {url}: {e}")
        return False

@dp.message(Command(commands=["yth"], prefix=BotCommands))
@new_task
async def yth(message: Message, bot: Bot):
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
            text="<b>❌ Provide a Valid YouTube link</b>",
            parse_mode=ParseMode.HTML
        )
        return
    youtube_url = message.text.split()[1].strip()
    logger.debug(f"Processing URL: {youtube_url}")
    fetching_msg = await send_message(
        chat_id=message.chat.id,
        text="<b>Fetching YouTube thumbnail...✨</b>",
        parse_mode=ParseMode.HTML
    )
    logger.debug(f"Sent fetching message {fetching_msg.message_id}")
    try:
        video_id = youtube_parser(youtube_url)
        if not video_id:
            await SmartAIO.edit_message_text(
                chat_id=message.chat.id,
                message_id=fetching_msg.message_id,
                text="<b>Invalid YouTube link Bro ❌</b>",
                parse_mode=ParseMode.HTML
            )
            return
        api_url = f"{A360APIBASEURL}/yt/dl?url={youtube_url}"
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as resp:
                if resp.status != 200:
                    raise Exception(f"API returned status {resp.status}")
                data = await resp.json()
        thumbnail_url = data.get("thumbnail")
        if not thumbnail_url:
            await SmartAIO.edit_message_text(
                chat_id=message.chat.id,
                message_id=fetching_msg.message_id,
                text="<b>No thumbnail available for this video ❌</b>",
                parse_mode=ParseMode.HTML
            )
            return
        os.makedirs("./downloads", exist_ok=True)
        file_path = f"./downloads/thumbnail_{video_id}.jpg"
        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail_url) as resp:
                if resp.status != 200:
                    raise Exception(f"Failed to download thumbnail: status {resp.status}")
                with open(file_path, "wb") as f:
                    f.write(await resp.read())
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=FSInputFile(file_path),
            caption="<code>Photo Sent</code>",
            parse_mode=ParseMode.HTML
        )
        await SmartAIO.delete_message(
            chat_id=message.chat.id,
            message_id=fetching_msg.message_id
        )
        clean_download(file_path)
        logger.info(f"Sent thumbnail for {youtube_url}")
    except Exception as e:
        logger.error(f"Error fetching YouTube thumbnail for URL {youtube_url}: {e}")
        await SmartAIO.edit_message_text(
            chat_id=message.chat.id,
            message_id=fetching_msg.message_id,
            text="<b>Sorry Bro YouTube Thumbnail API Dead</b>",
            parse_mode=ParseMode.HTML
        )
        if os.path.exists(file_path):
            clean_download(file_path)
        await Smart_Notify(bot, "/yth", e, message)