import aiohttp
import random
import os 
from io import BytesIO
from PIL import Image
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.enums import ParseMode
from bot import dp
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
import asyncio
import threading

user_daily_limits = {}
daily_limits_lock = threading.Lock()

async def upscale(buffer: bytes, width: int, height: int) -> tuple:
    try:
        random_number = random.randint(1_000_000, 999_999_999_999)
        form_data = aiohttp.FormData()
        form_data.add_field("image_file", buffer, filename="image.jpg", content_type="image/jpeg")
        form_data.add_field("name", str(random_number))
        form_data.add_field("desiredHeight", str(height * 4))
        form_data.add_field("desiredWidth", str(width * 4))
        form_data.add_field("outputFormat", "png")
        form_data.add_field("compressionLevel", "high")
        form_data.add_field("anime", "false")
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://upscalepics.com",
            "Referer": "https://upscalepics.com/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }
        async with aiohttp.ClientSession() as session:
            async with session.post("https://api.upscalepics.com/upscale-to-size", data=form_data, headers=headers) as response:
                if response.status == 200:
                    json_response = await response.json()
                    return json_response.get("bgRemoved", "").strip(), None
                else:
                    return None, f"API request failed with status {response.status}"
    except Exception as e:
        return None, f"Upscale error: {str(e)}"

@dp.message(Command(commands=["enh"], prefix=BotCommands))
@new_task
async def enh_handler(message: Message, bot: Bot):
    chat_id = message.chat.id
    user_id = message.from_user.id if message.from_user else None
    with daily_limits_lock:
        if user_id not in user_daily_limits:
            user_daily_limits[user_id] = 10
        if user_daily_limits[user_id] <= 0:
            await send_message(
                chat_id=chat_id,
                text="<b>You have reached your daily limit of 10 enhancements.</b>",
                parse_mode=ParseMode.HTML
            )
            return
    replied = message.reply_to_message
    valid_photo = replied and replied.photo
    valid_doc = replied and replied.document and replied.document.mime_type and replied.document.mime_type.startswith("image/")
    if not (valid_photo or valid_doc):
        await send_message(
            chat_id=chat_id,
            text="<b>Reply to a photo or image file to enhance face</b>",
            parse_mode=ParseMode.HTML
        )
        return
    temp_message = await send_message(
        chat_id=chat_id,
        text="<b>Enhancing Your Face....</b>",
        parse_mode=ParseMode.HTML
    )
    temp_files = []
    try:
        file_id = replied.photo[-1].file_id if valid_photo else replied.document.file_id
        file_info = await bot.get_file(file_id)
        file_path = f"temp_{random.randint(1_000_000, 999_999_999_999)}.jpg"
        await bot.download_file(file_info.file_path, file_path)
        if not os.path.exists(file_path):
            raise Exception("Failed to download image")
        temp_files.append(file_path)
        with open(file_path, 'rb') as f:
            image_buffer = f.read()
        with Image.open(BytesIO(image_buffer)) as img:
            width, height = img.size
        image_url, error = await upscale(image_buffer, width, height)
        clean_download(*temp_files)
        if image_url and image_url.startswith("http"):
            with daily_limits_lock:
                user_daily_limits[user_id] -= 1
            async with aiohttp.ClientSession() as session:
                async with session.get(image_url) as img_resp:
                    if img_resp.status == 200:
                        img_bytes = await img_resp.read()
                        if not img_bytes:
                            raise ValueError("Empty image data received from API")
                        img_path = f"enhanced_{random.randint(1_000_000, 999_999_999_999)}.png"
                        with open(img_path, 'wb') as f:
                            f.write(img_bytes)
                        temp_files.append(img_path)
                        try:
                            await delete_messages(chat_id, temp_message.message_id)
                        except Exception as e:
                            LOGGER.error(f"Failed to delete temp message in chat {chat_id}: {str(e)}")
                        await bot.send_document(
                            chat_id=chat_id,
                            document=FSInputFile(img_path),
                            caption=f"<b>✅ Face enhanced!</b>\n{user_daily_limits[user_id]} enhancements remaining today.",
                            parse_mode=ParseMode.HTML
                        )
                        clean_download(*temp_files)
                    else:
                        await temp_message.edit_text(
                            text="<b>Sorry Enhancer API Dead</b>",
                            parse_mode=ParseMode.HTML,
                            disable_web_page_preview=True
                        )
        else:
            await temp_message.edit_text(
                text="<b>Sorry Enhancer API Dead</b>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            if error:
                LOGGER.error(f"Enhancer error: {error}")
                await Smart_Notify(bot, "/enh", error, message)
    except Exception as e:
        LOGGER.error(f"Enhancer error: {str(e)}")
        await Smart_Notify(bot, "/enh", e, message)
        try:
            await temp_message.edit_text(
                text="<b>Sorry Enhancer API Dead</b>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
        except Exception as edit_e:
            LOGGER.error(f"Failed to edit temp message in chat {chat_id}: {str(edit_e)}")
            await send_message(
                chat_id=chat_id,
                text="<b>Sorry Enhancer API Dead</b>",
                parse_mode=ParseMode.HTML
            )
        clean_download(*temp_files)