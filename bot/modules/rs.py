import asyncio
import re
import shutil
import os
import subprocess
from PIL import Image
from aiogram import F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.enums import ParseMode, ChatType
from bot import dp, SmartAIO
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message
from bot.helpers.notify import Smart_Notify
from bot.helpers.logger import LOGGER
from bot.helpers.buttons import SmartButtons
from bot.helpers.commands import BotCommands
from bot.helpers.defend import SmartDefender
from bot import SmartPyro

logger = LOGGER
image_store = {}
image_store_lock = asyncio.Lock()
waiting_users = {}
waiting_users_lock = asyncio.Lock()

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
    "wide_banner": (1920, 480),
    "bot_father": (640, 360),
    "medium_thumb": (480, 270)
}

async def resize_image(input_path, width, height, user_id):
    output_path = f"./downloads/resized_{user_id}_{width}x{height}.png"
    try:
        with open(input_path, 'rb') as f:
            img = Image.open(f).convert("RGBA")
            resized = img.resize((width, height), Image.Resampling.LANCZOS)
            resized.save(output_path, "PNG", optimize=True)
    except Exception as e:
        logger.error(f"Error in resize_image: {e}")
        raise
    return output_path

async def resize_gif(input_path, width, height, user_id):
    output_path = f"./downloads/resized_{user_id}_{width}x{height}.gif"
    try:
        img = Image.open(input_path)
        if not getattr(img, "is_animated", False):
            img.close()
            raise ValueError("Not animated GIF")
        frames, durations = [], []
        try:
            while True:
                frame = img.copy().convert("RGBA").resize((width, height), Image.Resampling.LANCZOS)
                frames.append(frame)
                durations.append(img.info.get("duration", 100))
                img.seek(img.tell() + 1)
        except EOFError:
            pass
        img.close()
        if frames:
            frames[0].save(output_path, save_all=True, append_images=frames[1:], duration=durations, loop=0, optimize=True)
    except Exception as e:
        logger.error(f"Error in resize_gif: {e}")
        raise
    return output_path

async def resize_mp4(input_path, width, height, user_id):
    output_path = f"./downloads/resized_{user_id}_{width}x{height}.gif"
    try:
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black",
            "-r", "10",
            "-f", "gif",
            "-c:v", "gif",
            output_path
        ]
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"FFmpeg failed: {stderr.decode()}")
    except Exception as e:
        logger.error(f"Error in resize_mp4: {e}")
        raise
    return output_path

@dp.message(Command(commands=["rs", "res"], prefix=BotCommands))
@new_task
@SmartDefender
async def resize_menu_handler(message: Message, bot: Bot):
    if message.chat.type not in [ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP]:
        await send_message(
            chat_id=message.chat.id,
            text="<b>This command only works in private or group chats</b>",
            parse_mode=ParseMode.HTML
        )
        return
    user_id = message.from_user.id
    full_name = message.from_user.full_name or "Unknown"
    reply = message.reply_to_message
    if not reply or (not reply.photo and not reply.document and not reply.animation):
        await send_message(
            chat_id=message.chat.id,
            text="<b>Reply to a photo or an image file</b>",
            parse_mode=ParseMode.HTML
        )
        return
    file_id = None
    if reply.animation:
        file_id = reply.animation.file_id
    elif reply.document:
        file_id = reply.document.file_id
    elif reply.photo:
        file_id = reply.photo[-1].file_id
    logger.info(f"Received Image From User {full_name}")
    status_msg = await send_message(
        chat_id=message.chat.id,
        text="<b>Processing Your Image...</b>",
        parse_mode=ParseMode.HTML
    )
    temp_file = f"./downloads/temp_{user_id}_{int(asyncio.get_event_loop().time())}.tmp"
    original_file = None
    try:
        pyro_msg = await SmartPyro.get_messages(
            chat_id=reply.chat.id,
            message_ids=reply.message_id
        )
        if not pyro_msg:
            raise Exception("Failed to fetch message")
        downloaded_path = await SmartPyro.download_media(
            message=pyro_msg,
            file_name=temp_file
        )
        if not downloaded_path:
            raise Exception("Download failed")
        is_mp4 = False
        with open(downloaded_path, 'rb') as f:
            header = f.read(12)
            if header[4:12] in [b'ftypmp42', b'ftypisom', b'ftypiso2', b'ftypavc1', b'ftypmp4']:
                is_mp4 = True
        is_gif = False
        file_type = "unknown"
        if not is_mp4:
            try:
                with open(downloaded_path, 'rb') as f:
                    img = Image.open(f)
                    file_type = img.format
                    is_gif = getattr(img, "is_animated", False) and file_type == "GIF"
                    img.close()
            except Exception as e:
                logger.error(f"PIL detection failed: {e}")
        ext = ".mp4" if is_mp4 else (".gif" if is_gif else ".png")
        original_file = f"./downloads/res_{user_id}{ext}"
        shutil.move(downloaded_path, original_file)
        logger.info(f"File type detected: {file_type}, is_gif: {is_gif}, is_mp4: {is_mp4}")
        async with image_store_lock:
            image_store[user_id] = {"path": original_file, "is_gif": is_gif, "is_mp4": is_mp4}
        buttons = SmartButtons()
        buttons.button(text="❤️ DP Square", callback_data="resize_dp_square", position="header")
        buttons.button(text="💫 Widescreen", callback_data="resize_widescreen", position="header")
        buttons.button(text="⭐ Story", callback_data="resize_story", position="header")
        buttons.button(text="✨ Portrait", callback_data="resize_portrait", position="header")
        buttons.button(text="📰 Vertical", callback_data="resize_vertical", position="header")
        buttons.button(text="📖 Horizontal", callback_data="resize_horizontal", position="header")
        buttons.button(text="🧩 Standard", callback_data="resize_standard", position="header")
        buttons.button(text="🔥 IG Post", callback_data="resize_ig_post", position="header")
        buttons.button(text="👀 TikTok DP", callback_data="resize_tiktok_dp", position="header")
        buttons.button(text="🕸️ FB Cover", callback_data="resize_fb_cover", position="header")
        buttons.button(text="🕷️ YT Banner", callback_data="resize_yt_banner", position="header")
        buttons.button(text="👁️ YT Thumb", callback_data="resize_yt_thumb", position="header")
        buttons.button(text="🐦 X Header", callback_data="resize_x_header", position="header")
        buttons.button(text="⭐ X Post", callback_data="resize_x_post", position="header")
        buttons.button(text="🤖 LinkedIn Banner", callback_data="resize_linkedin_banner", position="header")
        buttons.button(text="❤️ WhatsApp DP", callback_data="resize_whatsapp_dp", position="header")
        buttons.button(text="💘 Small Thumb", callback_data="resize_small_thumb", position="header")
        buttons.button(text="🎥 Wide Banner", callback_data="resize_wide_banner", position="header")
        buttons.button(text="🐵 Bot Desc Photo", callback_data="resize_bot_father", position="header")
        buttons.button(text="✨ Medium Thumb", callback_data="resize_medium_thumb", position="header")
        buttons.button(text="⏰ GIF Resize", callback_data="resize_gif_resize", position="header")
        buttons.button(text="📰 Custom Size", callback_data="resize_custom_size", position="header")
        buttons.button(text="❌ Close", callback_data="resize_close", position="footer")
        reply_markup = buttons.build_menu(b_cols=2, h_cols=2, f_cols=1)
        await send_message(
            chat_id=message.chat.id,
            text="<b>Choose a format to resize the image:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error downloading image: {e}")
        await Smart_Notify(SmartAIO, "/rs", e, message)
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
@SmartDefender
async def resize_button_handler(callback_query: CallbackQuery, bot: Bot):
    user_id = callback_query.from_user.id
    chat_id = callback_query.message.chat.id
    data = callback_query.data.replace("resize_", "")
    async with image_store_lock:
        if user_id not in image_store:
            await callback_query.answer("Image not found. Please use /rs again.", show_alert=True)
            return
        input_path = image_store[user_id]["path"]
        is_gif = image_store[user_id]["is_gif"]
        is_mp4 = image_store[user_id]["is_mp4"]
    if data == "close":
        await SmartAIO.delete_message(
            chat_id=chat_id,
            message_id=callback_query.message.message_id
        )
        await callback_query.answer("Menu closed.")
        async with image_store_lock:
            image_store.pop(user_id, None)
        clean_download(input_path)
        return
    if is_gif or is_mp4:
        if data not in ["gif_resize", "custom_size"]:
            await callback_query.answer("Use GIF Resize or Custom Size for GIF/MP4", show_alert=True)
            return
    else:
        if data == "gif_resize":
            await callback_query.answer("GIF Resize is only for GIF/MP4 files", show_alert=True)
            return
    if data == "gif_resize":
        await SmartAIO.edit_message_text(
            chat_id=chat_id,
            message_id=callback_query.message.message_id,
            text="<b>Please Send Your Desired Size For GIF Like <code>1280x720</code></b>",
            parse_mode=ParseMode.HTML
        )
        async with waiting_users_lock:
            waiting_users[user_id] = {"input_path": input_path, "is_gif": is_gif, "is_mp4": is_mp4, "message_id": callback_query.message.message_id}
        await callback_query.answer()
        return
    if data == "custom_size":
        await SmartAIO.edit_message_text(
            chat_id=chat_id,
            message_id=callback_query.message.message_id,
            text="<b>Please Send Your Desired Size Like <code>1280x720</code></b>",
            parse_mode=ParseMode.HTML
        )
        async with waiting_users_lock:
            waiting_users[user_id] = {"input_path": input_path, "is_gif": is_gif, "is_mp4": is_mp4, "message_id": callback_query.message.message_id}
        await callback_query.answer()
        return
    width, height = RESOLUTIONS.get(data, (1080, 1080))
    output_file = None
    try:
        logger.info(f"Processing Image Resize.....")
        if is_gif:
            output_file = await resize_gif(input_path, width, height, user_id)
        elif is_mp4:
            output_file = await resize_mp4(input_path, width, height, user_id)
        else:
            output_file = await resize_image(input_path, width, height, user_id)
        logger.info(f"Processing Done Uploading......")
        await SmartAIO.delete_message(chat_id=chat_id, message_id=callback_query.message.message_id)
        await SmartAIO.send_document(
            chat_id=chat_id,
            document=FSInputFile(output_file),
            caption=f"<b>Resized to {width}x{height}</b>",
            parse_mode=ParseMode.HTML
        )
        await callback_query.answer(f"Image successfully resized to {width}x{height}!")
    except Exception as e:
        logger.error(f"Resizing error: {e}")
        await Smart_Notify(SmartAIO, "/rs", e, callback_query.message)
        await callback_query.answer("Failed to resize image.", show_alert=True)
    finally:
        async with image_store_lock:
            image_store.pop(user_id, None)
        if output_file:
            clean_download(input_path, output_file)
        else:
            clean_download(input_path)

@dp.message(F.text.regexp(r'^\d+x\d+$'))
@new_task
@SmartDefender
async def custom_size_handler(message: Message, bot: Bot):
    user_id = message.from_user.id
    full_name = message.from_user.full_name or "Unknown"
    async with waiting_users_lock:
        if user_id not in waiting_users:
            return
        wait_data = waiting_users.pop(user_id)
    if not message.text:
        await message.reply("Please send the size in text format like 1280x720")
        return
    text = message.text.strip()
    if not re.match(r'^\d+x\d+$', text):
        await message.reply("Invalid format. Please send like 1280x720")
        return
    width, height = map(int, text.split('x'))
    if width <= 0 or height <= 0 or width > 10000 or height > 10000:
        await message.reply("Size must be between 1-10000")
        return
    input_path = wait_data["input_path"]
    is_gif = wait_data["is_gif"]
    is_mp4 = wait_data["is_mp4"]
    prompt_msg_id = wait_data["message_id"]
    output_file = None
    try:
        logger.info(f"Received Custom Size From User {full_name}")
        logger.info(f"Processing Image Resize.....")
        if is_gif:
            output_file = await resize_gif(input_path, width, height, user_id)
        elif is_mp4:
            output_file = await resize_mp4(input_path, width, height, user_id)
        else:
            output_file = await resize_image(input_path, width, height, user_id)
        logger.info(f"Processing Done Uploading......")
        await SmartAIO.delete_message(chat_id=message.chat.id, message_id=prompt_msg_id)
        await SmartAIO.send_document(
            chat_id=message.chat.id,
            document=FSInputFile(output_file),
            caption=f"<b>Resized to {width}x{height}</b>",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Resizing error: {e}")
        await message.reply("Failed to resize.")
    finally:
        async with image_store_lock:
            image_store.pop(user_id, None)
        if output_file:
            clean_download(input_path, output_file)
        else:
            clean_download(input_path)