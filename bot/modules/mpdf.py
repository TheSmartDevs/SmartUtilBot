import asyncio
import os
import tempfile
import time
from datetime import datetime
from typing import Dict

from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.enums import ParseMode, ChatType
from pypdf import PdfReader, PdfWriter

from bot import dp
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.buttons import SmartButtons
from bot.helpers.logger import LOGGER
from bot.helpers.utils import new_task, clean_download
from bot.helpers.notify import Smart_Notify
from bot.helpers.defend import SmartDefender

DOWNLOADS_DIR = "./downloads"
MAX_PDFS = 10
MAX_FILE_SIZE = 50 * 1024 * 1024
SESSION_TIMEOUT = 300

user_sessions: Dict[int, 'UserSession'] = {}

class UserSession:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.pdfs = []
        self.custom_title = None
        self.last_activity = datetime.now()
        self.user_dir = os.path.join(DOWNLOADS_DIR, str(user_id))
        self.awaiting_title = False
        self.message_id = None
        os.makedirs(self.user_dir, exist_ok=True)
        os.makedirs(DOWNLOADS_DIR, exist_ok=True)
    
    def add_pdf(self, file_path: str, file_name: str, file_size: int, file_id: str):
        self.pdfs.append({
            'path': file_path,
            'name': file_name,
            'size': file_size,
            'file_id': file_id
        })
        self.last_activity = datetime.now()
    
    def is_duplicate(self, file_id: str) -> bool:
        for pdf in self.pdfs:
            if pdf['file_id'] == file_id:
                return True
        return False
    
    def get_total_size(self) -> int:
        return sum(pdf['size'] for pdf in self.pdfs)
    
    def clear_pdfs(self):
        for pdf in self.pdfs:
            try:
                if os.path.exists(pdf['path']):
                    clean_download(pdf['path'])
                    LOGGER.info(f"Deleted file: {pdf['path']}")
            except Exception as e:
                LOGGER.error(f"Error deleting file {pdf['path']}: {e}")
        self.pdfs = []
        self.custom_title = None
        self.awaiting_title = False
    
    def cleanup(self):
        self.clear_pdfs()
        try:
            if os.path.exists(self.user_dir):
                for file in os.listdir(self.user_dir):
                    if file.endswith('.pdf'):
                        file_path = os.path.join(self.user_dir, file)
                        try:
                            clean_download(file_path)
                            LOGGER.info(f"Cleaned up file: {file_path}")
                        except Exception as e:
                            LOGGER.error(f"Error cleaning up file {file_path}: {e}")
                LOGGER.info(f"Cleaned up files in directory: {self.user_dir}")
        except Exception as e:
            LOGGER.error(f"Error cleaning up directory {self.user_dir}: {e}")

def get_keyboard(pdf_count: int):
    buttons = SmartButtons()
    buttons.button(f"📄 PDFs Added: {pdf_count}/10", f"pdf_count:{pdf_count}", position="header")
    buttons.button("🔄 Reorder PDFs", "reorder")
    buttons.button("✏️ Set Title", "set_title")
    buttons.button("✅ Merge Now", "merge_now")
    buttons.button("🗑 Clear All", "clear_all")
    buttons.button("❌ Cancel", "cancel", position="footer")
    return buttons.build_menu(b_cols=2, h_cols=1, f_cols=1)

def get_cancel_keyboard():
    buttons = SmartButtons()
    buttons.button("❌ Cancel", "cancel_title")
    return buttons.build_menu(b_cols=1)

def format_size(size_bytes: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

@dp.message(Command(commands=["mpdf"], prefix=BotCommands))
@new_task
@SmartDefender
async def mpdf_command(message: Message, bot: Bot):
    user_id = message.from_user.id
    
    if user_id in user_sessions:
        user_sessions[user_id].cleanup()
        LOGGER.info(f"Cleaned up existing session for user {user_id}")
    
    user_sessions[user_id] = UserSession(user_id)
    
    LOGGER.info(f"User {user_id} started PDF merge session")
    
    try:
        sent_msg = await send_message(
            chat_id=message.chat.id,
            text=(
                "<b>📄 PDF Merger</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                "<b>📤 Send PDF Files:</b>\n"
                "Send me 2 or more PDF files to merge.\n\n"
                "<b>⚙️ Features:</b>\n"
                "• Merge up to 10 PDFs\n"
                "• Custom order selection\n"
                "• Set custom title\n"
                "• Maintains quality\n"
                "• Max 50 MB per file\n\n"
                "<b>📝 Instructions:</b>\n"
                "1️⃣ Send PDF files one by one\n"
                "2️⃣ Reorder files if needed\n"
                "3️⃣ Set custom title (optional)\n"
                "4️⃣ Click '✅ Merge Now'\n\n"
                "⏱️ Session expires in 5 minutes"
            ),
            reply_markup=get_keyboard(0),
            parse_mode=ParseMode.HTML
        )
        
        user_sessions[user_id].message_id = sent_msg.message_id
        LOGGER.info(f"PDF Merger prompt sent to user {user_id}")
    except Exception as e:
        await Smart_Notify(bot, "mpdf_command", e, message)
        LOGGER.error(f"Failed to start PDF Merger for user {user_id}: {e}")

@dp.message(lambda m: m.from_user.id in user_sessions and m.document and not user_sessions[m.from_user.id].awaiting_title)
@new_task
@SmartDefender
async def handle_document(message: Message, bot: Bot):
    user_id = message.from_user.id
    
    if user_id not in user_sessions:
        await send_message(
            chat_id=message.chat.id,
            text="<b>Please use /mpdf to start a merge session first!</b>",
            parse_mode=ParseMode.HTML
        )
        return
    
    session = user_sessions[user_id]
    
    if session.awaiting_title:
        return
    
    document = message.document
    
    if not document.file_name.lower().endswith('.pdf'):
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Please send only PDF files!</b>",
            parse_mode=ParseMode.HTML
        )
        return
    
    if document.file_size > MAX_FILE_SIZE:
        await send_message(
            chat_id=message.chat.id,
            text=f"<b>❌ File too large! Max size is {format_size(MAX_FILE_SIZE)}</b>",
            parse_mode=ParseMode.HTML
        )
        return
    
    if len(session.pdfs) >= MAX_PDFS:
        await send_message(
            chat_id=message.chat.id,
            text=f"<b>❌ Maximum {MAX_PDFS} PDFs allowed!</b>",
            parse_mode=ParseMode.HTML
        )
        return
    
    if session.is_duplicate(document.file_id):
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ This PDF has already been added! Skipping duplicate.</b>",
            parse_mode=ParseMode.HTML
        )
        LOGGER.info(f"User {user_id} tried to add duplicate PDF: {document.file_name}")
        return
    
    download_msg = await send_message(
        chat_id=message.chat.id,
        text="<b>Downloading Received PDFs 📄...</b>",
        parse_mode=ParseMode.HTML
    )
    
    try:
        os.makedirs(session.user_dir, exist_ok=True)
        
        timestamp = int(time.time())
        safe_filename = document.file_name.rsplit('.', 1)[0].replace('/', '_').replace('\\', '_')
        file_path = os.path.join(session.user_dir, f"{safe_filename}_{timestamp}.pdf")
        
        file = await bot.get_file(document.file_id)
        await bot.download_file(file.file_path, file_path)
        
        session.add_pdf(file_path, document.file_name, document.file_size, document.file_id)
        
        await delete_messages(message.chat.id, download_msg.message_id)
        
        pdf_count = len(session.pdfs)
        total_size = session.get_total_size()
        
        LOGGER.info(f"User {user_id} added PDF: {document.file_name} ({format_size(document.file_size)})")
        
        success_msg = await send_message(
            chat_id=message.chat.id,
            text=(
                f"<b>✅ PDF Added Successfully!</b>\n\n"
                f"<b>📄 File:</b> {document.file_name}\n"
                f"<b>📦 Size:</b> {format_size(document.file_size)}\n"
                f"<b>📊 Total PDFs:</b> {pdf_count}/{MAX_PDFS}\n"
                f"<b>💾 Total Size:</b> {format_size(total_size)}\n\n"
                f"Send more PDFs"
            ),
            reply_markup=get_keyboard(pdf_count),
            parse_mode=ParseMode.HTML
        )
        
        if session.message_id:
            try:
                await delete_messages(message.chat.id, session.message_id)
            except:
                pass
        
        session.message_id = success_msg.message_id
        
    except Exception as e:
        await Smart_Notify(bot, "handle_document", e, message)
        LOGGER.error(f"Error downloading PDF for user {user_id}: {e}")
        await delete_messages(message.chat.id, download_msg.message_id)
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Error downloading PDF. Please try again.</b>",
            parse_mode=ParseMode.HTML
        )

@dp.message(lambda m: m.from_user.id in user_sessions and m.text and user_sessions[m.from_user.id].awaiting_title)
@new_task
@SmartDefender
async def handle_text(message: Message, bot: Bot):
    user_id = message.from_user.id
    
    if user_id not in user_sessions:
        return
    
    session = user_sessions[user_id]
    
    if session.awaiting_title:
        title = message.text.strip()
        session.custom_title = title
        session.awaiting_title = False
        
        LOGGER.info(f"User {user_id} set custom title: {title}")
        
        await delete_messages(message.chat.id, message.message_id)
        
        pdf_count = len(session.pdfs)
        total_size = session.get_total_size()
        
        last_pdf = session.pdfs[-1] if session.pdfs else None
        
        try:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=session.message_id,
                text=(
                    f"<b>✅ PDF Added Successfully!</b>\n\n"
                    f"<b>📄 File:</b> {last_pdf['name'] if last_pdf else 'None'}\n"
                    f"<b>📦 Size:</b> {format_size(last_pdf['size']) if last_pdf else '0 B'}\n"
                    f"<b>📊 Total PDFs:</b> {pdf_count}/{MAX_PDFS}\n"
                    f"<b>💾 Total Size:</b> {format_size(total_size)}\n"
                    f"<b>✏️ Custom Title:</b> {title}\n\n"
                    f"Send more PDFs"
                ),
                reply_markup=get_keyboard(pdf_count),
                parse_mode=ParseMode.HTML
            )
        except Exception as e:
            await Smart_Notify(bot, "handle_text", e, message)
            LOGGER.error(f"Error editing message for user {user_id}: {e}")

@dp.callback_query(lambda c: c.from_user.id in user_sessions)
async def handle_callback(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    data = callback.data
    
    LOGGER.info(f"User {user_id} clicked button: {data}")
    
    if user_id not in user_sessions:
        await callback.answer("Session expired! Use /mpdf to start again.", show_alert=True)
        return
    
    session = user_sessions[user_id]
    pdf_count = len(session.pdfs)
    
    try:
        if data.startswith("pdf_count:"):
            await callback.answer(f"You Have Added {pdf_count}/10 PDFs")
            return
        
        if data == "clear_all":
            session.clear_pdfs()
            LOGGER.info(f"User {user_id} cleared all PDFs")
            await callback.answer("🗑️ All PDFs Cleared", show_alert=True)
            await callback.message.edit_text(
                "<b>🗑️ All PDFs Cleared</b>\n\n"
                "Use <code>/mpdf</code> to start again",
                parse_mode=ParseMode.HTML
            )
            return
        
        if data == "cancel":
            session.cleanup()
            del user_sessions[user_id]
            LOGGER.info(f"User {user_id} cancelled PDF merge session")
            await callback.message.edit_text(
                "<b>❌ PDF merge cancelled.</b>",
                parse_mode=ParseMode.HTML
            )
            await callback.answer()
            return
        
        if pdf_count < 2 and data in ["reorder", "set_title", "merge_now"]:
            await callback.answer("Please Atleast Add 2 PDFs ❌", show_alert=True)
            return
        
        if data == "reorder":
            await callback.answer("Reorder feature coming soon!", show_alert=True)
            return
        
        if data == "set_title":
            session.awaiting_title = True
            await callback.message.edit_text(
                "<b>✏️ Set Custom Title</b>\n\n"
                "Send me the title for your merged PDF:\n\n"
                "<b>Example:</b>\n"
                "<code>My Documents</code>\n"
                "<code>Report 2025</code>\n"
                "<code>Combined Files</code>\n\n"
                "The title will be used as filename",
                reply_markup=get_cancel_keyboard(),
                parse_mode=ParseMode.HTML
            )
            await callback.answer()
            return
        
        if data == "cancel_title":
            session.awaiting_title = False
            total_size = session.get_total_size()
            last_pdf = session.pdfs[-1] if session.pdfs else None
            await callback.message.edit_text(
                f"<b>✅ PDF Added Successfully!</b>\n\n"
                f"<b>📄 File:</b> {last_pdf['name'] if last_pdf else 'None'}\n"
                f"<b>📦 Size:</b> {format_size(last_pdf['size']) if last_pdf else '0 B'}\n"
                f"<b>📊 Total PDFs:</b> {pdf_count}/{MAX_PDFS}\n"
                f"<b>💾 Total Size:</b> {format_size(total_size)}\n\n"
                f"Send more PDFs",
                reply_markup=get_keyboard(pdf_count),
                parse_mode=ParseMode.HTML
            )
            await callback.answer()
            return
        
        if data == "merge_now":
            await callback.message.delete()
            
            merge_msg = await send_message(
                chat_id=callback.message.chat.id,
                text="<b>Merging Your PDFs.....🕣</b>",
                parse_mode=ParseMode.HTML
            )
            
            try:
                start_time = time.time()
                
                merger = PdfWriter()
                
                for pdf in session.pdfs:
                    LOGGER.info(f"Adding PDF to merger: {pdf['path']}")
                    reader = PdfReader(pdf['path'])
                    for page in reader.pages:
                        merger.add_page(page)
                
                output_filename = session.custom_title if session.custom_title else f"Merged_PDF_{int(datetime.now().timestamp())}"
                if not output_filename.endswith('.pdf'):
                    output_filename += '.pdf'
                
                output_path = os.path.join(session.user_dir, output_filename)
                
                with open(output_path, 'wb') as output_file:
                    merger.write(output_file)
                
                merger.close()
                
                LOGGER.info(f"User {user_id} merged {pdf_count} PDFs into {output_filename}")
                
                await merge_msg.edit_text(
                    "<b>Uploading On Telegram....🌐</b>",
                    parse_mode=ParseMode.HTML
                )
                
                file_size = os.path.getsize(output_path)
                time_taken = time.time() - start_time
                
                await bot.send_document(
                    chat_id=callback.message.chat.id,
                    document=FSInputFile(output_path, filename=output_filename),
                    caption=(
                        f"<b>✅ PDF Merged Successfully!</b>\n\n"
                        f"<b>📄 Filename:</b> {output_filename}\n"
                        f"<b>📊 Total PDFs Merged:</b> {pdf_count}\n"
                        f"<b>💾 File Size:</b> {format_size(file_size)}\n"
                        f"<b>⏱️ Time Taken:</b> {time_taken:.2f}s"
                    ),
                    parse_mode=ParseMode.HTML
                )
                
                await delete_messages(callback.message.chat.id, merge_msg.message_id)
                
                if os.path.exists(output_path):
                    try:
                        clean_download(output_path)
                        LOGGER.info(f"Deleted merged output file: {output_path}")
                    except Exception as e:
                        LOGGER.error(f"Error deleting output file: {e}")
                
                session.cleanup()
                del user_sessions[user_id]
                
                LOGGER.info(f"User {user_id} session cleaned up successfully")
                
            except Exception as e:
                await Smart_Notify(bot, "merge_now", e)
                LOGGER.error(f"Error merging PDFs for user {user_id}: {e}")
                await merge_msg.edit_text(f"❌ Error merging PDFs: {str(e)}")
                session.cleanup()
                del user_sessions[user_id]
    
    except Exception as e:
        await Smart_Notify(bot, "handle_callback", e)
        LOGGER.error(f"Error handling callback for user {user_id}: {e}")
        await callback.answer("❌ An error occurred!", show_alert=True)