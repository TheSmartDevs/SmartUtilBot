# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
#  Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
import os
import aiohttp
import aiofiles
import asyncio
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.enums import ParseMode, ChatType
from bot import dp, SmartAIO
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.notify import Smart_Notify
from bot.helpers.logger import LOGGER
from bot.helpers.buttons import SmartButtons
from bot.helpers.commands import BotCommands
from bot.helpers.defend import SmartDefender

logger = LOGGER
API_KEY = "23nfCEipDijgVv6SH14oktJe"
user_daily_limits = {}
daily_limits_lock = asyncio.Lock()

def generate_unique_filename(base_name: str) -> str:
    if os.path.exists(base_name):
        count = 1
        name, ext = os.path.splitext(base_name)
        while True:
            new_name = f"{name}_{count}{ext}"
            if not os.path.exists(new_name):
                return new_name
            count += 1
    return base_name

async def remove_bg(buffer: bytes, user_id: int) -> tuple:
    headers = {"X-API-Key": API_KEY}
    try:
        async with aiohttp.ClientSession() as session:
            form_data = aiohttp.FormData()
            form_data.add_field("image_file", buffer, filename="image.png", content_type="image/png")
            async with session.post("https://api.remove.bg/v1.0/removebg", headers=headers, data=form_data) as resp:
                if "image" not in resp.headers.get("content-type", ""):
                    return False, await resp.json()
                os.makedirs("./downloads", exist_ok=True)
                output_filename = f"./downloads/no_bg_{user_id}.png"
                output_filename = generate_unique_filename(output_filename)
                async with aiofiles.open(output_filename, "wb") as out_file:
                    await out_file.write(await resp.read())
                return True, output_filename
    except Exception as e:
        return False, {"title": "Unknown Error", "errors": [{"detail": str(e)}]}

@dp.message(Command(commands=["rmbg"], prefix=BotCommands))
@new_task
@SmartDefender
async def rmbg_handler(message: Message, bot: Bot):
    if message.chat.type not in [ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP]:
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ This command only works in private or group chats</b>",
            parse_mode=ParseMode.HTML
        )
        return
    
    user_id = message.from_user.id
    logger.info(f"Command received from user {user_id} in chat {message.chat.id}: {message.text}")
    
    async with daily_limits_lock:
        if user_id not in user_daily_limits:
            user_daily_limits[user_id] = 10
        if user_daily_limits[user_id] <= 0:
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ You have reached your daily limit of 10 background removals.</b>",
                parse_mode=ParseMode.HTML
            )
            return
    
    reply = message.reply_to_message
    valid_photo = reply and reply.photo
    valid_doc = reply and reply.document and reply.document.mime_type and reply.document.mime_type.startswith("image/")
    
    if not (valid_photo or valid_doc):
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Reply to a photo or image file to remove background</b>",
            parse_mode=ParseMode.HTML
        )
        return
    
    if reply.document:
        mime_type = reply.document.mime_type
        file_name = reply.document.file_name
        if not (mime_type in ["image/jpeg", "image/png", "image/jpg"] or
                (file_name and file_name.lower().endswith((".jpg", ".jpeg", ".png")))):
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Invalid Image Provided</b>",
                parse_mode=ParseMode.HTML
            )
            return
    
    loading_message = await send_message(
        chat_id=message.chat.id,
        text="<b>Removing background...</b>",
        parse_mode=ParseMode.HTML
    )
    
    output_filename = None
    try:
        file_id = reply.photo[-1].file_id if valid_photo else reply.document.file_id
        os.makedirs("./downloads", exist_ok=True)
        temp_file = f"./downloads/temp_{user_id}.jpg"
        
        await bot.download(file=file_id, destination=temp_file)
        
        async with aiofiles.open(temp_file, "rb") as f:
            buffer = await f.read()
        
        success, result = await remove_bg(buffer, user_id)
        
        if not success:
            await SmartAIO.edit_message_text(
                chat_id=message.chat.id,
                message_id=loading_message.message_id,
                text="<b>❌ Sorry Bro Removal Failed</b>",
                parse_mode=ParseMode.HTML
            )
            await Smart_Notify(bot, "/rmbg", result, message)
            return
        
        output_filename = result
        
        async with daily_limits_lock:
            user_daily_limits[user_id] -= 1
            remaining = user_daily_limits[user_id]
        
        await bot.send_document(
            chat_id=message.chat.id,
            document=FSInputFile(output_filename),
            caption=f"<b>✅ Background removed!</b>\n<i>{remaining} removals remaining today.</i>",
            parse_mode=ParseMode.HTML
        )
        
        try:
            await SmartAIO.delete_message(
                chat_id=message.chat.id,
                message_id=loading_message.message_id
            )
        except Exception:
            pass
            
    except Exception as e:
        logger.error(f"rmbg error: {str(e)}")
        try:
            await SmartAIO.edit_message_text(
                chat_id=message.chat.id,
                message_id=loading_message.message_id,
                text="<b>❌ Sorry Bro Removal Failed</b>",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Sorry Bro Removal Failed</b>",
                parse_mode=ParseMode.HTML
            )
        await Smart_Notify(bot, "/rmbg", e, message)
    finally:
        try:
            temp_file = f"./downloads/temp_{user_id}.jpg"
            if os.path.exists(temp_file):
                clean_download(temp_file)
            if output_filename and os.path.exists(output_filename):
                clean_download(output_filename)
        except Exception as cleanup_error:
            logger.warning(f"Cleanup error for user {user_id}: {cleanup_error}")