import os
import asyncio
import time
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ParseMode, ChatType
from aiogram.exceptions import TelegramBadRequest
from pyrogram.enums import ParseMode as SmartParseMode
from bot import dp, SmartPyro
from bot.helpers.utils import new_task
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.buttons import SmartButtons
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.defend import SmartDefender
from pypdf import PdfWriter
from PIL import Image

user_sessions = {}
MAX_FILE_SIZE_MB = 500
SESSION_TIMEOUT = 180

def clean_pdf_download(*files):
    for file in files:
        try:
            if os.path.exists(file):
                os.remove(file)
                LOGGER.info(f"Cleaning Download - {file}")
        except Exception as e:
            LOGGER.error(f"Failed to clean download {file}: {e}")

def get_file_size_mb(filepath):
    size_bytes = os.path.getsize(filepath)
    size_mb = size_bytes / (1024 * 1024)
    return size_mb

def format_size(size_mb):
    if size_mb < 1:
        return f"{size_mb * 1024:.2f} KB"
    return f"{size_mb:.2f} MB"

def resize_image(img, max_dimension):
    width, height = img.size
    if width > max_dimension or height > max_dimension:
        ratio = min(max_dimension / width, max_dimension / height)
        new_size = (int(width * ratio), int(height * ratio))
        return img.resize(new_size, Image.LANCZOS)
    return img

def compress_pdf(input_path, output_path, max_dimension, jpeg_quality, compression_level):
    writer = PdfWriter(clone_from=input_path)
    
    for page in writer.pages:
        for img in page.images:
            try:
                pil_image = img.image
                
                if pil_image.mode == 'CMYK':
                    pil_image = pil_image.convert('RGB')
                elif pil_image.mode in ('RGBA', 'LA'):
                    background = Image.new('RGB', pil_image.size, (255, 255, 255))
                    if pil_image.mode == 'RGBA':
                        background.paste(pil_image, mask=pil_image.split()[3])
                    else:
                        background.paste(pil_image, mask=pil_image.split()[1])
                    pil_image = background
                elif pil_image.mode == 'P':
                    pil_image = pil_image.convert('RGB')
                elif pil_image.mode not in ('RGB', 'L'):
                    pil_image = pil_image.convert('RGB')
                
                resized_image = resize_image(pil_image, max_dimension)
                
                img.replace(resized_image, quality=jpeg_quality)
            except Exception:
                continue
        
        page.compress_content_streams(level=compression_level)
    
    writer.compress_identical_objects(remove_identicals=True, remove_orphans=True)
    
    with open(output_path, "wb") as f:
        writer.write(f)

def compress_pdf_extreme(input_path, output_path):
    compress_pdf(input_path, output_path, max_dimension=800, jpeg_quality=30, compression_level=9)

def compress_pdf_recommended(input_path, output_path):
    compress_pdf(input_path, output_path, max_dimension=1400, jpeg_quality=65, compression_level=9)

def compress_pdf_low(input_path, output_path):
    compress_pdf(input_path, output_path, max_dimension=1920, jpeg_quality=75, compression_level=6)

async def cancel_session(user_id):
    if user_id in user_sessions:
        session = user_sessions[user_id]
        if session.get('file_path') and os.path.exists(session['file_path']):
            clean_pdf_download(session['file_path'])
        if session.get('timeout_task'):
            session['timeout_task'].cancel()
        del user_sessions[user_id]

async def session_timeout(user_id, message_id, chat_id, bot):
    await asyncio.sleep(SESSION_TIMEOUT)
    if user_id in user_sessions:
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text="<b>⏱️ Session expired due to inactivity</b>",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass
        await cancel_session(user_id)

@dp.message(Command(commands=["cpdf"], prefix=BotCommands))
@new_task
@SmartDefender
async def cpdf_handler(message: Message, bot: Bot):
    LOGGER.info(f"Received /cpdf command from user {message.from_user.id} in chat {message.chat.id}")
    
    try:
        if message.chat.type != ChatType.PRIVATE:
            await send_message(
                chat_id=message.chat.id,
                text="<b>⚠️ PDF compress works only in private chat</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"User {message.from_user.id} tried to use /cpdf in non-private chat")
            return
        
        await cancel_session(message.from_user.id)
        
        buttons = SmartButtons()
        buttons.button(text="❌ Cancel", callback_data="cpdf_cancel")
        reply_markup = buttons.build_menu(b_cols=1)
        
        initial_text = (
            "<b>Smart PDF Compressor By SmartDev</b>\n"
            "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
            "<b>📤 Send me a PDF file to compress</b>\n\n"
            "<b>⚙️ Available Options:</b>\n"
            "• 🔥 Extreme - Maximum compression\n"
            "• ⚡ Recommended - Balanced quality\n"
            "• 💎 Low - Best quality\n\n"
            "<b>📝 Note: Max file size 500 MB</b>\n\n"
            "<i>Session expires in 3 minutes</i>"
        )
        
        sent_message = await send_message(
            chat_id=message.chat.id,
            text=initial_text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        
        timeout_task = asyncio.create_task(session_timeout(
            message.from_user.id, 
            sent_message.message_id, 
            message.chat.id, 
            bot
        ))
        
        user_sessions[message.from_user.id] = {
            'state': 'waiting_file',
            'message_id': sent_message.message_id,
            'timeout_task': timeout_task
        }
        
        LOGGER.info(f"PDF compression session started for user {message.from_user.id}")
        
    except Exception as e:
        LOGGER.error(f"Error in cpdf_handler: {e}")
        await Smart_Notify(bot, "cpdf", e, message)

@dp.message(lambda message: message.from_user.id in user_sessions and user_sessions[message.from_user.id].get('state') == 'waiting_file')
async def handle_pdf_upload(message: Message, bot: Bot):
    user_id = message.from_user.id
    
    try:
        if not message.document:
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Please send a valid PDF file</b>",
                parse_mode=ParseMode.HTML
            )
            return
        
        if not message.document.file_name.lower().endswith('.pdf'):
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Please send a PDF file only</b>",
                parse_mode=ParseMode.HTML
            )
            return
        
        file_size_mb = message.document.file_size / (1024 * 1024)
        
        if file_size_mb > MAX_FILE_SIZE_MB:
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Sorry Bro Max File Size Limit 500 MB</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"User {user_id} sent oversized PDF: {file_size_mb:.2f} MB")
            return
        
        progress_msg = await send_message(
            chat_id=message.chat.id,
            text="<b>Downloading Received PDF ⬇️</b>",
            parse_mode=ParseMode.HTML
        )
        
        file_path = await SmartPyro.download_media(message.document.file_id, file_name=f"{int(time.time())}.pdf")
        
        LOGGER.info(f"Downloaded PDF for user {user_id}: {file_path}")
        
        buttons = SmartButtons()
        buttons.button(text="🔥 Extreme", callback_data="cpdf_extreme")
        buttons.button(text="⚡ Recommended", callback_data="cpdf_recommended")
        buttons.button(text="💎 Low", callback_data="cpdf_low")
        buttons.button(text="❌ Cancel", callback_data="cpdf_cancel")
        reply_markup = buttons.build_menu(b_cols=1)
        
        selection_text = (
            "<b>✅ PDF Ready to Compress</b>\n\n"
            f"<b>📄 File:</b> <code>{message.document.file_name}</code>\n"
            f"<b>📦 Size:</b> <code>{format_size(file_size_mb)}</code>\n\n"
            "<b>Select compression level:</b>"
        )
        
        await progress_msg.edit_text(
            text=selection_text,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        
        user_sessions[user_id].update({
            'state': 'waiting_mode',
            'file_path': file_path,
            'file_name': message.document.file_name,
            'original_size': file_size_mb,
            'selection_message_id': progress_msg.message_id
        })
        
        if user_sessions[user_id].get('timeout_task'):
            user_sessions[user_id]['timeout_task'].cancel()
        
        timeout_task = asyncio.create_task(session_timeout(
            user_id, 
            progress_msg.message_id, 
            message.chat.id, 
            bot
        ))
        user_sessions[user_id]['timeout_task'] = timeout_task
        
    except Exception as e:
        LOGGER.error(f"Error handling PDF upload: {e}")
        await Smart_Notify(bot, "cpdf_upload", e, message)
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Error processing PDF file</b>",
            parse_mode=ParseMode.HTML
        )
        await cancel_session(user_id)

@dp.callback_query(lambda c: c.data.startswith("cpdf_"))
async def handle_cpdf_callback(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    
    try:
        await callback.answer()
        
        if callback.data == "cpdf_cancel":
            await callback.message.edit_text(
                text="<b>❌ Cancelled Smart PDF Compressor</b>",
                parse_mode=ParseMode.HTML
            )
            await cancel_session(user_id)
            LOGGER.info(f"User {user_id} cancelled PDF compression")
            return
        
        if user_id not in user_sessions:
            await callback.message.edit_text(
                text="<b>⚠️ Session expired. Please start again with /cpdf</b>",
                parse_mode=ParseMode.HTML
            )
            return
        
        session = user_sessions[user_id]
        
        if session.get('state') != 'waiting_mode':
            return
        
        mode = callback.data.replace("cpdf_", "")
        
        await callback.message.edit_text(
            text="<b>Compressing Received PDF Size...📄</b>",
            parse_mode=ParseMode.HTML
        )
        
        input_path = session['file_path']
        output_path = f"{os.path.splitext(input_path)[0]}_compressed_{mode}.pdf"
        
        if mode == "extreme":
            compress_pdf_extreme(input_path, output_path)
            quality_text = "Extreme"
        elif mode == "recommended":
            compress_pdf_recommended(input_path, output_path)
            quality_text = "Recommended"
        elif mode == "low":
            compress_pdf_low(input_path, output_path)
            quality_text = "Low"
        
        compressed_size = get_file_size_mb(output_path)
        original_size = session['original_size']
        reduction = ((original_size - compressed_size) / original_size) * 100
        
        caption = (
            "<b>✅ PDF Compressed Successfully</b>\n"
            "<b>━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>📄 Original Size:</b> <code>{format_size(original_size)}</code>\n"
            f"<b>📦 Compressed Size:</b> <code>{format_size(compressed_size)}</code>\n"
            f"<b>📉 Reduction:</b> <code>{reduction:.1f}%</code>\n"
            f"<b>⚙️ Quality:</b> <code>{quality_text}</code>\n"
            "<b>━━━━━━━━━━━━━━━━━━</b>\n"
            "<b>Thank You For Using Our Smart Bot</b>"
        )
        
        await SmartPyro.send_document(
            chat_id=callback.message.chat.id,
            document=output_path,
            caption=caption,
            parse_mode=SmartParseMode.HTML
        )
        
        await callback.message.delete()
        
        clean_pdf_download(input_path, output_path)
        
        await cancel_session(user_id)
        
        LOGGER.info(f"Successfully compressed PDF for user {user_id} with {mode} mode")
        
    except Exception as e:
        LOGGER.error(f"Error in cpdf callback: {e}")
        await Smart_Notify(bot, "cpdf_callback", e, None)
        try:
            await callback.message.edit_text(
                text="<b>❌ Error compressing PDF file</b>",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass
        await cancel_session(user_id)