# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
#  Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
import os
import re
import uuid
import asyncio
from PIL import Image
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, BufferedInputFile, FSInputFile, InputSticker
from aiogram.enums import ParseMode, StickerFormat, StickerType
from aiogram.exceptions import TelegramBadRequest
from bot import dp
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.buttons import SmartButtons
from bot.helpers.defend import SmartDefender

FILE_LOCK = asyncio.Lock()

def get_emoji_regex():
    try:
        import emoji
        emoji_pattern = r'[\U0001F600-\U0001F64F]|[\U0001F300-\U0001F5FF]|[\U0001F680-\U0001F6FF]|[\U0001F1E0-\U0001F1FF]|[\U00002600-\U000027BF]|[\U0001F900-\U0001F9FF]|[\U0001F018-\U0001F270]'
        return re.compile(emoji_pattern)
    except:
        return re.compile(r'[\U0001F600-\U0001F64F]|[\U0001F300-\U0001F5FF]|[\U0001F680-\U0001F6FF]|[\U0001F1E0-\U0001F1FF]|[\U00002600-\U000027BF]|[\U0001F900-\U0001F9FF]|[\U0001F018-\U0001F270]')

EMOJI_PATTERN = get_emoji_regex()

async def resize_png_for_sticker(input_file: str, output_file: str):
    async with FILE_LOCK:
        try:
            with Image.open(input_file) as im:
                width, height = im.size
                if width == 512 or height == 512:
                    im.save(output_file, "PNG", optimize=True)
                    return output_file
                if width > height:
                    new_width = 512
                    new_height = int((512 / width) * height)
                else:
                    new_height = 512
                    new_width = int((512 / height) * width)
                im = im.resize((new_width, new_height), Image.Resampling.LANCZOS)
                im.save(output_file, "PNG", optimize=True)
                return output_file
        except Exception as e:
            LOGGER.error(f"Error resizing PNG: {str(e)}")
            return None

async def process_video_sticker(input_file: str, output_file: str):
    try:
        command = [
            "ffmpeg", "-i", input_file,
            "-t", "3",
            "-vf", "scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:(ow-iw)/2:(oh-ih)/2,fps=24",
            "-c:v", "libvpx-vp9", "-crf", "34", "-b:v", "150k",
            "-an", "-y",
            output_file
        ]
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            LOGGER.error(f"FFmpeg error: {stderr.decode()}")
            return None
        async with FILE_LOCK:
            if os.path.exists(output_file) and os.path.getsize(output_file) > 256 * 1024:
                LOGGER.info("File size exceeds 256KB, re-encoding with lower quality")
                command[-3] = "-b:v"
                command[-2] = "100k"
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                if process.returncode != 0:
                    LOGGER.error(f"FFmpeg error: {stderr.decode()}")
                    return None
        return output_file
    except Exception as e:
        LOGGER.error(f"Error processing video: {str(e)}")
        return None

async def process_gif_to_webm(input_file: str, output_file: str):
    try:
        command = [
            "ffmpeg", "-i", input_file,
            "-t", "3",
            "-vf", "scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:(ow-iw)/2:(oh-ih)/2,fps=24",
            "-c:v", "libvpx-vp9", "-crf", "34", "-b:v", "150k",
            "-an", "-y",
            output_file
        ]
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            LOGGER.error(f"FFmpeg error: {stderr.decode()}")
            return None
        async with FILE_LOCK:
            if os.path.exists(output_file) and os.path.getsize(output_file) > 256 * 1024:
                LOGGER.info("File size exceeds 256KB, re-encoding with lower quality")
                command[-3] = "-b:v"
                command[-2] = "100k"
                process = await asyncio.create_subprocess_exec(
                    *command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                if process.returncode != 0:
                    LOGGER.error(f"FFmpeg error: {stderr.decode()}")
                    return None
        return output_file
    except Exception as e:
        LOGGER.error(f"Error processing GIF: {str(e)}")
        return None

@dp.message(Command(commands=["kang"], prefix=BotCommands))
@new_task
@SmartDefender
async def kang_handler(message: Message, bot: Bot):
    user_id = message.from_user.id if message.from_user else 'Unknown'
    chat_id = message.chat.id
    LOGGER.info(f"Received /kang command from user: {user_id}")
    temp_message = None
    temp_files = []
    try:
        if not message.reply_to_message:
            temp_message = await send_message(
                chat_id=chat_id,
                text="<b>Please reply to a sticker, image, or document to kang it!</b>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            LOGGER.warning(f"No reply message provided by user: {user_id}")
            return

        temp_message = await send_message(
            chat_id=chat_id,
            text="<b>Kanging this Sticker...✨</b>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )

        packnum = 1
        packname = f"a{user_id}_by_{(await bot.get_me()).username}"
        max_stickers = 120

        async def check_sticker_set():
            nonlocal packnum, packname
            while packnum <= 100:
                try:
                    stickerset = await bot.get_sticker_set(name=packname)
                    if len(stickerset.stickers) < max_stickers:
                        return True
                    packnum += 1
                    packname = f"a{packnum}_{user_id}_by_{(await bot.get_me()).username}"
                except TelegramBadRequest:
                    return False
            return False

        packname_found = await check_sticker_set()
        if not packname_found and packnum > 100:
            await temp_message.edit_text(
                text="<b>❌ Maximum sticker packs reached!</b>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            LOGGER.warning(f"Maximum sticker packs reached for user: {user_id}")
            return

        reply = message.reply_to_message
        file_id = None
        sticker_format = "static"

        if reply.sticker:
            file_id = reply.sticker.file_id
            if reply.sticker.is_animated:
                sticker_format = "animated"
            elif reply.sticker.is_video:
                sticker_format = "video"
            else:
                sticker_format = "static"
        elif reply.photo:
            file_id = reply.photo[-1].file_id
            sticker_format = "static"
        elif reply.document:
            file_id = reply.document.file_id
            if reply.document.mime_type == "image/gif":
                sticker_format = "gif"
            elif reply.document.mime_type in ["video/webm", "video/mp4"]:
                sticker_format = "video"
            else:
                sticker_format = "static"
        elif reply.animation:
            file_id = reply.animation.file_id
            sticker_format = "gif"
        else:
            await temp_message.edit_text(
                text="<b>Please reply to a valid sticker, image, GIF, or document!</b>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            LOGGER.warning(f"Invalid reply type for user: {user_id}")
            return

        try:
            file_name = f"kangsticker_{uuid.uuid4().hex}"
            if sticker_format == "animated":
                file_extension = ".tgs"
            elif sticker_format in ["video", "gif"]:
                file_extension = ".webm" if sticker_format == "video" else ".gif"
            else:
                file_extension = ".png"

            file_path = f"{file_name}{file_extension}"
            file_info = await bot.get_file(file_id)
            await bot.download_file(file_info.file_path, file_path)

            if not os.path.exists(file_path):
                await temp_message.edit_text(
                    text="<b>❌ Failed To Kang The Sticker</b>",
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
                LOGGER.error(f"Failed to download file for user: {user_id}")
                return

            temp_files.append(file_path)

        except Exception as e:
            LOGGER.error(f"Download error for user {user_id}: {str(e)}")
            await Smart_Notify(bot, "/kang", e, message)
            await temp_message.edit_text(
                text="<b>❌ Failed To Kang The Sticker</b>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            for file in temp_files:
                clean_download(file)
            return

        sticker_emoji = "🌟"
        args = get_args(message)
        if len(args) > 0:
            emoji_matches = "".join(set(EMOJI_PATTERN.findall(" ".join(args))))
            sticker_emoji = emoji_matches or sticker_emoji
        elif reply.sticker and reply.sticker.emoji:
            sticker_emoji = reply.sticker.emoji

        full_name = message.from_user.first_name
        if message.from_user.last_name:
            full_name += f" {message.from_user.last_name}"
        pack_title = f"{full_name}'s Pack"

        try:
            final_file = file_path
            final_format = StickerFormat.STATIC

            if sticker_format == "static":
                output_file = f"resized_{uuid.uuid4().hex}.png"
                processed_file = await resize_png_for_sticker(file_path, output_file)
                if not processed_file:
                    await temp_message.edit_text(
                        text="<b>❌ Failed To Kang The Sticker</b>",
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True
                    )
                    LOGGER.error(f"Failed to resize PNG for user: {user_id}")
                    for file in temp_files:
                        clean_download(file)
                    return
                final_file = processed_file
                final_format = StickerFormat.STATIC
                temp_files.append(final_file)

            elif sticker_format == "gif":
                output_file = f"compressed_{uuid.uuid4().hex}.webm"
                processed_file = await process_gif_to_webm(file_path, output_file)
                if not processed_file:
                    await temp_message.edit_text(
                        text="<b>❌ Failed To Kang The Sticker</b>",
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True
                    )
                    LOGGER.error(f"Failed to process GIF for user: {user_id}")
                    for file in temp_files:
                        clean_download(file)
                    return
                final_file = processed_file
                final_format = StickerFormat.VIDEO
                temp_files.append(final_file)

            elif sticker_format == "video":
                output_file = f"compressed_{uuid.uuid4().hex}.webm"
                processed_file = await process_video_sticker(file_path, output_file)
                if not processed_file:
                    await temp_message.edit_text(
                        text="<b>❌ Failed To Kang The Sticker</b>",
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True
                    )
                    LOGGER.error(f"Failed to process video for user: {user_id}")
                    for file in temp_files:
                        clean_download(file)
                    return
                final_file = processed_file
                final_format = StickerFormat.VIDEO
                temp_files.append(final_file)

            elif sticker_format == "animated":
                final_format = StickerFormat.ANIMATED

            with open(final_file, 'rb') as f:
                file_data = f.read()

            input_sticker = InputSticker(
                sticker=BufferedInputFile(
                    file_data,
                    filename=os.path.basename(final_file)
                ),
                format=final_format,
                emoji_list=[sticker_emoji]
            )

            try:
                await bot.add_sticker_to_set(
                    user_id=user_id,
                    name=packname,
                    sticker=input_sticker
                )
                success = True
            except TelegramBadRequest:
                try:
                    await bot.create_new_sticker_set(
                        user_id=user_id,
                        name=packname,
                        title=pack_title,
                        stickers=[input_sticker],
                        sticker_type=StickerType.REGULAR
                    )
                    success = True
                except Exception as e:
                    LOGGER.error(f"Error creating sticker set for user {user_id}: {str(e)}")
                    success = False
            except Exception as e:
                LOGGER.error(f"Error adding sticker for user {user_id}: {str(e)}")
                success = False

            if success:
                buttons = SmartButtons()
                buttons.button(text="View Sticker Pack", url=f"t.me/addstickers/{packname}")
                await temp_message.edit_text(
                    text=f"<b>Sticker Kanged! </b>\n<b>Emoji: {sticker_emoji}</b>\n<b>Pack: {pack_title}</b>",
                    parse_mode=ParseMode.HTML,
                    reply_markup=buttons.build_menu(b_cols=2),
                    disable_web_page_preview=True
                )
                LOGGER.info(f"Successfully kanged sticker for user: {user_id}")
            else:
                await temp_message.edit_text(
                    text="<b>❌ Failed To Kang The Sticker</b>",
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
                LOGGER.error(f"Failed to add/create sticker set for user: {user_id}")

        except Exception as e:
            LOGGER.error(f"Processing error for user {user_id}: {str(e)}")
            await Smart_Notify(bot, "/kang", e, message)
            await temp_message.edit_text(
                text="<b>❌ Failed To Kang The Sticker</b>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )

        finally:
            for file in temp_files:
                clean_download(file)

    except Exception as e:
        LOGGER.error(f"Error in /kang for user {user_id}: {str(e)}")
        await Smart_Notify(bot, "/kang", e, message)
        error_text = "<b>❌ Failed To Kang The Sticker</b>"
        if temp_message:
            try:
                await temp_message.edit_text(
                    text=error_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
                LOGGER.info(f"Edited temp message with error in chat {chat_id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit temp message in chat {chat_id}: {str(edit_e)}")
                await Smart_Notify(bot, "/kang", edit_e, message)
                await send_message(
                    chat_id=chat_id,
                    text=error_text,
                    parse_mode=ParseMode.HTML
                )
        else:
            await send_message(
                chat_id=chat_id,
                text=error_text,
                parse_mode=ParseMode.HTML
            )
        LOGGER.info(f"Sent error message to chat {chat_id}")
        for file in temp_files:

            clean_download(file)
