import aiofiles
import os
import asyncio
from PIL import Image
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.enums import ParseMode, ChatType
from bot import dp, SmartAIO
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.notify import Smart_Notify
from bot.helpers.logger import LOGGER
from bot.helpers.buttons import SmartButtons
from bot.helpers.commands import BotCommands

logger = LOGGER

image_store = {}
image_store_lock = asyncio.Lock()

RESOLUTIONS = {
    "dp_square": (1080, 1080),
    "widescreen": (1920, 1080),
    "story": (1080, 1920),
    "portrait": (1080, 1620),
    "vertical": (1080, 2160),
    "horizontal": (2160, 1080),
    "standard": (1620, 1080),
    "ig_post": (1080, 1080),
    "tiktok_dp": (200, 200),
    "fb_cover": (820, 312),
    "yt_banner": (2560, 1440),
    "yt_thumb": (1280, 720),
    "x_header": (1500, 500),
    "x_post": (1600, 900),
    "linkedin_banner": (1584, 396),
    "whatsapp_dp": (500, 500),
    "small_thumb": (320, 180),
    "medium_thumb": (480, 270),
    "wide_banner": (1920, 480),
    "bot_father": (640, 360)
}

async def resize_image(input_path, width, height, user_id):
    output_path = f"./downloads/resized_{user_id}_{width}x{height}.jpg"
    os.makedirs("./downloads", exist_ok=True)
    try:
        async with aiofiles.open(input_path, mode='rb') as f:
            img = Image.open(f.name)
            resized = img.resize((width, height), Image.Resampling.LANCZOS)
            resized.save(output_path, format="JPEG", quality=95, optimize=True)
            img.close()
    except Exception as e:
        logger.error(f"Error in resize_image: {e}")
        raise
    return output_path

@dp.message(Command(commands=["rs", "res"], prefix=BotCommands))
@new_task
async def resize_menu_handler(message: Message, bot: Bot):
    if message.chat.type not in [ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP]:
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ This command only works in private or group chats</b>",
            parse_mode=ParseMode.HTML
        )
        return
    user_id = message.from_user.id
    logger.info(f"Command received from user {user_id} in chat {message.chat.id}: {message.text}")
    reply = message.reply_to_message
    if not reply or (not reply.photo and not reply.document):
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Reply to a photo or an image file</b>",
            parse_mode=ParseMode.HTML
        )
        return
    if reply.document:
        mime_type = reply.document.mime_type
        file_name = reply.document.file_name
        if not (mime_type in ["image/jpeg", "image/png"] or 
                (file_name and file_name.lower().endswith((".jpg", ".jpeg", ".png")))):
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Invalid Image Provided</b>",
                parse_mode=ParseMode.HTML
            )
            return
    status_msg = await send_message(
        chat_id=message.chat.id,
        text="<b>Resizing Your Image...</b>",
        parse_mode=ParseMode.HTML
    )
    try:
        file_id = reply.photo[-1].file_id if reply.photo else reply.document.file_id
        os.makedirs("./downloads", exist_ok=True)
        original_file = f"./downloads/res_{user_id}.jpg"
        await bot.download(file=file_id, destination=original_file)
        async with image_store_lock:
            image_store[user_id] = original_file
        logger.info(f"[{user_id}] Image saved to {original_file}")
        buttons = SmartButtons()
        buttons.button(text="1:1 DP Square", callback_data="resize_dp_square", position="header")
        buttons.button(text="16:9 Widescreen", callback_data="resize_widescreen", position="header")
        buttons.button(text="9:16 Story", callback_data="resize_story", position="header")
        buttons.button(text="2:3 Portrait", callback_data="resize_portrait", position="header")
        buttons.button(text="1:2 Vertical", callback_data="resize_vertical", position="header")
        buttons.button(text="2:1 Horizontal", callback_data="resize_horizontal", position="header")
        buttons.button(text="3:2 Standard", callback_data="resize_standard", position="header")
        buttons.button(text="IG Post", callback_data="resize_ig_post", position="header")
        buttons.button(text="TikTok DP", callback_data="resize_tiktok_dp", position="header")
        buttons.button(text="FB Cover", callback_data="resize_fb_cover", position="header")
        buttons.button(text="YT Banner", callback_data="resize_yt_banner", position="header")
        buttons.button(text="YT Thumb", callback_data="resize_yt_thumb", position="header")
        buttons.button(text="X Header", callback_data="resize_x_header", position="header")
        buttons.button(text="X Post", callback_data="resize_x_post", position="header")
        buttons.button(text="LinkedIn Banner", callback_data="resize_linkedin_banner", position="header")
        buttons.button(text="WhatsApp DP", callback_data="resize_whatsapp_dp", position="header")
        buttons.button(text="Small Thumb", callback_data="resize_small_thumb", position="header")
        buttons.button(text="Medium Thumb", callback_data="resize_medium_thumb", position="header")
        buttons.button(text="Wide Banner", callback_data="resize_wide_banner", position="header")
        buttons.button(text="Bot Father", callback_data="resize_bot_father", position="header")
        buttons.button(text="❌ Close", callback_data="resize_close", position="footer")
        reply_markup = buttons.build_menu(b_cols=2, h_cols=2, f_cols=1)
        await send_message(
            chat_id=message.chat.id,
            text="<b>🔧 Choose a format to resize the image:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"[{user_id}] Error downloading image: {e}")
        await Smart_Notify(bot, "/rs", e, message)
        await send_message(
            chat_id=message.chat.id,
            text="<b>This Image Can Not Be Resized</b>",
            parse_mode=ParseMode.HTML
        )
    finally:
        await SmartAIO.delete_message(
            chat_id=message.chat.id,
            message_id=status_msg.message_id
        )

@dp.callback_query(lambda c: c.data.startswith("resize_"))
@new_task
async def resize_button_handler(callback_query: CallbackQuery, bot: Bot):
    user_id = callback_query.from_user.id
    chat_id = callback_query.message.chat.id
    data = callback_query.data.replace("resize_", "")
    if data == "close":
        await SmartAIO.delete_message(
            chat_id=chat_id,
            message_id=callback_query.message.message_id
        )
        await callback_query.answer("Menu closed.")
        return
    async with image_store_lock:
        if user_id not in image_store:
            await callback_query.answer("⚠️ Image not found. Please use /rs again.", show_alert=True)
            return
        input_path = image_store[user_id]
    width, height = RESOLUTIONS.get(data, (1080, 1080))
    try:
        output_file = await resize_image(input_path, width, height, user_id)
        await bot.send_document(
            chat_id=chat_id,
            document=FSInputFile(output_file),
            caption=f"<b>✔️ Resized to {width}x{height}</b>",
            parse_mode=ParseMode.HTML
        )
        await callback_query.answer(f"Image successfully resized to {width}x{height}!")
    except Exception as e:
        logger.error(f"[{user_id}] Resizing error: {e}")
        await Smart_Notify(bot, "/rs", e, callback_query.message)
        await callback_query.answer("Failed to resize image.", show_alert=True)
    finally:
        async with image_store_lock:
            image_store.pop(user_id, None)
        try:
            if os.path.exists(input_path):
                clean_download(input_path)
            if 'output_file' in locals() and os.path.exists(output_file):
                clean_download(output_file)
        except Exception as e:
            logger.warning(f"[{user_id}] Cleanup error: {e}")