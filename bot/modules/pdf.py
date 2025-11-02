import asyncio
import os
import tempfile
import time
from datetime import datetime
from io import BytesIO
from typing import Dict

from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.enums import ParseMode, ChatType
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from pypdf import PdfReader, PdfWriter

from bot import dp
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.buttons import SmartButtons
from bot.helpers.logger import LOGGER
from bot.helpers.utils import new_task, clean_download
from bot.helpers.notify import Smart_Notify
from bot.helpers.defend import SmartDefender

user_states: Dict[int, Dict] = {}
user_data: Dict[int, Dict] = {}

PAGE_SIZES = {"a4": "A4", "auto": "Auto Fit"}
DPI_OPTIONS = {72: "Web (72)", 150: "Standard (150)", 300: "Print (300)", 600: "High (600)"}
FIT_MODES = {"shrink": "Shrink To Fit", "crop": "Crop To Fit"}
PAGE_NUMBER_POS = {
    "top_left": "Top Left",
    "top_center": "Top Center",
    "top_right": "Top Right",
    "bottom_left": "Bottom Left",
    "bottom_center": "Bottom Center",
    "bottom_right": "Bottom Right"
}
COVER_TEMPLATES = {"clean": "Clean", "bold": "Bold", "minimal": "Minimal"}

def get_state(user_id: int) -> str:
    return user_states.get(user_id, {}).get("state", "")

def set_state(user_id: int, state: str):
    if user_id not in user_states:
        user_states[user_id] = {}
    user_states[user_id]["state"] = state

def clear_state(user_id: int):
    user_states.pop(user_id, None)
    user_data.pop(user_id, None)

def get_data(user_id: int) -> Dict:
    return user_data.get(user_id, {})

def set_data(user_id: int, data: Dict):
    user_data[user_id] = data

def get_initial_message(title: str) -> str:
    return (
        "<b>📄 Professional PDF Maker</b>\n\n"
        f"<b>Title:</b> {title}\n"
        "<b>Max Images:</b> 100\n\n"
        "<b>⚙️ Configure your PDF:</b>\n\n"
        "<b>📄 Page Size</b> - A4 or Auto Fit\n"
        "<b>🖨️ DPI</b> - Web (72), Standard (150), Print (300), High (600)\n"
        "<b>📐 Fit Mode</b> - Shrink or Crop to Fit\n"
        "<b>🔢 Page Numbers</b> - Add page numbering\n"
        "<b>📕 Cover Page</b> - Multiple templates available\n"
        "<b>💧 Watermark</b> - Add text watermark\n"
        "<b>🔐 Password</b> - Protect your PDF\n\n"
        "Select your preferences and click <b>Start Processing!</b>"
    )

def get_settings_message(data: Dict) -> str:
    page_size = PAGE_SIZES[data["page_size"]]
    dpi_text = DPI_OPTIONS[data["dpi"]]
    fit_text = FIT_MODES[data["fit_mode"]]
    page_nums = f"<code>{PAGE_NUMBER_POS[data['page_numbers']]}</code>" if data["page_numbers"] else "No"
    cover = f"<code>{COVER_TEMPLATES[data['cover_page']]}</code>" if data["cover_page"] else "No"
    watermark = f"<code>{data['watermark']}</code>" if data["watermark"] else "No"
    password = "Set" if data["password"] else "No"

    return (
        "<b>📄 Professional PDF Maker</b>\n\n"
        f"<b>Title:</b> {data['title']}\n"
        "<b>Max Images:</b> 100\n\n"
        "<b>⚙️ Configure your PDF:</b>\n\n"
        "<b>📄 Page Size</b> - A4 or Auto Fit\n"
        "<b>🖨️ DPI</b> - Web (72), Standard (150), Print (300), High (600)\n"
        "<b>📐 Fit Mode</b> - Shrink or Crop to Fit\n"
        "<b>🔢 Page Numbers</b> - Add page numbering\n"
        "<b>📕 Cover Page</b> - Multiple templates available\n"
        "<b>💧 Watermark</b> - Add text watermark\n"
        "<b>🔐 Password</b> - Protect your PDF\n\n"
        "Select your preferences and click <b>Start Processing!</b>"
    )

def build_main_keyboard(data: Dict):
    buttons = SmartButtons()

    a4_text = "✅ A4" if data["page_size"] == "a4" else "📄 A4"
    auto_text = "✅ Auto" if data["page_size"] == "auto" else "🔄 Auto"
    buttons.button(a4_text, "pdf_page_a4")
    buttons.button(auto_text, "pdf_page_auto")

    dpi_web = "✅ Web (72)" if data["dpi"] == 72 else "🌐 Web (72)"
    dpi_standard = "✅ Standard (150)" if data["dpi"] == 150 else "📱 Standard (150)"
    dpi_print = "✅ Print (300)" if data["dpi"] == 300 else "🖨 Print (300)"
    dpi_high = "✅ High (600)" if data["dpi"] == 600 else "🙊 High (600)"
    buttons.button(dpi_web, "pdf_dpi_72")
    buttons.button(dpi_standard, "pdf_dpi_150")
    buttons.button(dpi_print, "pdf_dpi_300")
    buttons.button(dpi_high, "pdf_dpi_600")

    shrink_text = "✅ Shrink To Fit" if data["fit_mode"] == "shrink" else "🤖 Shrink To Fit"
    crop_text = "✅ Crop To Fit" if data["fit_mode"] == "crop" else "⚖ Crop To Fit"
    buttons.button(shrink_text, "pdf_fit_shrink")
    buttons.button(crop_text, "pdf_fit_crop")

    page_nums = "✅ Page Numbers" if data["page_numbers"] else "🔢 Page Numbers"
    buttons.button(page_nums, "pdf_page_numbers")

    cover = "✅ Cover Page" if data["cover_page"] else "🅰 Cover Page"
    buttons.button(cover, "pdf_cover_page")

    watermark = "✅ Watermark" if data["watermark"] else "💧 Watermark"
    password = "✅ Password" if data["password"] else "🔒 Password"
    buttons.button(watermark, "pdf_watermark")
    buttons.button(password, "pdf_password")

    buttons.button("▶️ Start Processing", "pdf_start_processing", position="footer")

    return buttons.build_menu(b_cols=2, f_cols=1)

def build_page_numbers_keyboard():
    buttons = SmartButtons()
    buttons.button("↖️ Top Left", "pdf_pn_top_left")
    buttons.button("⬆️ Top Center", "pdf_pn_top_center")
    buttons.button("↗️ Top Right", "pdf_pn_top_right")
    buttons.button("↙️ Bottom Left", "pdf_pn_bottom_left")
    buttons.button("⬇️ Bottom Center", "pdf_pn_bottom_center")
    buttons.button("↘️ Bottom Right", "pdf_pn_bottom_right")
    buttons.button("◀️ Back To Settings", "pdf_back_settings", position="footer")
    return buttons.build_menu(b_cols=3, f_cols=1)

def build_cover_keyboard():
    buttons = SmartButtons()
    buttons.button("✨ Clean", "pdf_cover_clean")
    buttons.button("⚡️ Bold", "pdf_cover_bold")
    buttons.button("🎨 Minimal", "pdf_cover_minimal")
    buttons.button("◀️ Back To Settings", "pdf_back_settings", position="footer")
    return buttons.build_menu(b_cols=3, f_cols=1)

def build_back_keyboard():
    buttons = SmartButtons()
    buttons.button("◀️ Back To Settings", "pdf_back_settings")
    return buttons.build_menu(b_cols=1)

def build_collection_keyboard(count: int):
    buttons = SmartButtons()
    buttons.button(f"✅ Generate PDF ({count})", "pdf_generate")
    buttons.button("❌ Cancel", "pdf_cancel")
    return buttons.build_menu(b_cols=2)

@dp.message(Command(commands=["pdf"], prefix=BotCommands))
@new_task
@SmartDefender
async def pdf_handler(message: Message, bot: Bot):
    user_id = message.from_user.id

    if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await send_message(
            chat_id=message.chat.id,
            text="<b>⚠️ PDF can only be created in private chat.</b>",
            parse_mode=ParseMode.HTML
        )
        LOGGER.info(f"User {user_id} tried to use /pdf in group chat")
        return

    LOGGER.info(f"User {user_id} started /pdf command")

    try:
        args = get_args(message)
        title = args[0] if args else "Document"
        data = {
            "title": title,
            "page_size": "auto",
            "dpi": 150,
            "fit_mode": "shrink",
            "page_numbers": None,
            "cover_page": None,
            "watermark": None,
            "password": None,
            "images": []
        }
        set_data(user_id, data)
        set_state(user_id, "pdf_settings")

        await send_message(
            chat_id=message.chat.id,
            text=get_initial_message(title),
            reply_markup=build_main_keyboard(data),
            parse_mode=ParseMode.HTML
        )
        LOGGER.info(f"PDF prompt sent to user {user_id}")
    except Exception as e:
        await Smart_Notify(bot, "pdf_handler", e, message)
        LOGGER.error(f"Failed to start PDF handler for user {user_id}: {e}")
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Failed to start PDF maker!</b>",
            parse_mode=ParseMode.HTML
        )

@dp.callback_query(lambda c: c.data == "pdf_cancel")
async def pdf_cancel(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    LOGGER.info(f"User {user_id} cancelled PDF generation")

    try:
        await callback.message.edit_text(
            "<b>🚫 PDF Creation Cancelled!</b>",
            parse_mode=ParseMode.HTML
        )
        clear_state(user_id)
        await callback.answer()
        LOGGER.info(f"Cancelled PDF generation for user {user_id}")
    except Exception as e:
        await Smart_Notify(bot, "pdf_cancel", e)
        LOGGER.error(f"Failed to cancel for user {user_id}: {e}")
        await callback.answer("❌ Failed to cancel!", show_alert=True)

@dp.callback_query(lambda c: c.data.startswith("pdf_page_"))
async def pdf_page_size(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    if get_state(user_id) != "pdf_settings":
        await callback.answer("Session expired!", show_alert=True)
        return

    size = callback.data.split("_")[-1]
    data = get_data(user_id)
    if data["page_size"] == size:
        await callback.answer("Already selected 😒", show_alert=True)
        return

    data["page_size"] = size
    set_data(user_id, data)
    await callback.message.edit_text(
        text=get_settings_message(data),
        reply_markup=build_main_keyboard(data),
        parse_mode=ParseMode.HTML
    )
    await callback.answer(f"Page Resized To {PAGE_SIZES[size].upper()}")

@dp.callback_query(lambda c: c.data.startswith("pdf_dpi_"))
async def pdf_dpi(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    if get_state(user_id) != "pdf_settings":
        await callback.answer("Session expired!", show_alert=True)
        return

    dpi = int(callback.data.split("_")[-1])
    data = get_data(user_id)
    if data["dpi"] == dpi:
        dpi_names = {72: "Web (72)", 150: "Standard (150)", 300: "Print (300)", 600: "High (600)"}
        await callback.answer(f"{dpi_names[dpi]} Already Selected 😒", show_alert=True)
        return

    data["dpi"] = dpi
    set_data(user_id, data)
    await callback.message.edit_text(
        text=get_settings_message(data),
        reply_markup=build_main_keyboard(data),
        parse_mode=ParseMode.HTML
    )
    await callback.answer(f"DPI Successfully Changed To {dpi}")

@dp.callback_query(lambda c: c.data in ["pdf_fit_shrink", "pdf_fit_crop"])
async def pdf_fit_mode(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    if get_state(user_id) != "pdf_settings":
        await callback.answer("Session expired!", show_alert=True)
        return

    mode = callback.data.split("_")[-1]
    data = get_data(user_id)
    if data["fit_mode"] == mode:
        await callback.answer(f"{FIT_MODES[mode]} Already Selected 😒", show_alert=True)
        return

    data["fit_mode"] = mode
    set_data(user_id, data)
    await callback.message.edit_text(
        text=get_settings_message(data),
        reply_markup=build_main_keyboard(data),
        parse_mode=ParseMode.HTML
    )
    await callback.answer(f"Fit Mode Changed To {mode.capitalize()}")

@dp.callback_query(lambda c: c.data == "pdf_page_numbers")
async def pdf_page_numbers(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    data = get_data(user_id)
    if data["page_numbers"]:
        data["page_numbers"] = None
        set_data(user_id, data)
        await callback.message.edit_reply_markup(reply_markup=build_main_keyboard(data))
        await callback.answer("Page Numbering Disabled")
    else:
        text = "<b>🔢 Page Number Position</b>\n\nSelect where you want page numbers:"
        await callback.message.edit_text(text, reply_markup=build_page_numbers_keyboard())

@dp.callback_query(lambda c: c.data.startswith("pdf_pn_"))
async def pdf_page_number_pos(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    pos = callback.data.replace("pdf_pn_", "")
    data = get_data(user_id)
    data["page_numbers"] = pos
    set_data(user_id, data)
    await callback.message.edit_text(
        text=get_settings_message(data),
        reply_markup=build_main_keyboard(data),
        parse_mode=ParseMode.HTML
    )
    position_names = {
        "top_left": "Top Left", "top_center": "Top Center", "top_right": "Top Right",
        "bottom_left": "Bottom Left", "bottom_center": "Bottom Center", "bottom_right": "Bottom Right"
    }
    await callback.answer(f"Page Numbers Set To {position_names[pos]}")

@dp.callback_query(lambda c: c.data == "pdf_cover_page")
async def pdf_cover_page(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    data = get_data(user_id)
    if data["cover_page"]:
        data["cover_page"] = None
        set_data(user_id, data)
        await callback.message.edit_reply_markup(reply_markup=build_main_keyboard(data))
        await callback.answer("Cover Page Disabled")
    else:
        text = "<b>📕 Cover Page Template</b>\n\nSelect a cover design theme:"
        await callback.message.edit_text(text, reply_markup=build_cover_keyboard())

@dp.callback_query(lambda c: c.data.startswith("pdf_cover_"))
async def pdf_cover_template(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    template = callback.data.replace("pdf_cover_", "")
    data = get_data(user_id)
    data["cover_page"] = template
    set_data(user_id, data)
    await callback.message.edit_text(
        text=get_settings_message(data),
        reply_markup=build_main_keyboard(data),
        parse_mode=ParseMode.HTML
    )
    await callback.answer(f"Cover Page Set To {template.capitalize()}")

@dp.callback_query(lambda c: c.data == "pdf_watermark")
async def pdf_watermark(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    data = get_data(user_id)
    if data["watermark"]:
        data["watermark"] = None
        set_data(user_id, data)
        await callback.message.edit_reply_markup(reply_markup=build_main_keyboard(data))
        await callback.answer("Watermark Disabled")
    else:
        text = (
            "<b>💧 Watermark Text</b>\n\n"
            "Send me the text you want as watermark.\n"
            "Example: Confidential, Draft, your name, etc.\n\n"
            "Click 'Back to Settings' to continue without watermark."
        )
        await callback.message.edit_text(text, reply_markup=build_back_keyboard())
        set_state(user_id, "waiting_watermark")

@dp.message(lambda m: get_state(m.from_user.id) == "waiting_watermark" and m.text)
@new_task
@SmartDefender
async def process_watermark(message: Message, bot: Bot):
    user_id = message.from_user.id
    data = get_data(user_id)
    data["watermark"] = message.text
    set_data(user_id, data)
    await delete_messages(message.chat.id, message.message_id)
    await send_message(
        message.chat.id,
        get_settings_message(data),
        reply_markup=build_main_keyboard(data),
        parse_mode=ParseMode.HTML
    )
    set_state(user_id, "pdf_settings")

@dp.callback_query(lambda c: c.data == "pdf_password")
async def pdf_password(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    data = get_data(user_id)
    if data["password"]:
        data["password"] = None
        set_data(user_id, data)
        await callback.message.edit_reply_markup(reply_markup=build_main_keyboard(data))
        await callback.answer("Password Protection Disabled")
    else:
        text = (
            "<b>🔐 PDF Password</b>\n\n"
            "Send me the password to protect your PDF.\n"
            "Min 4 characters, max 50 characters.\n"
            "Example: secure123, mypassword, etc.\n\n"
            "Click 'Back to Settings' to skip password protection."
        )
        await callback.message.edit_text(text, reply_markup=build_back_keyboard())
        set_state(user_id, "waiting_password")

@dp.message(lambda m: get_state(m.from_user.id) == "waiting_password" and m.text)
@new_task
@SmartDefender
async def process_password(message: Message, bot: Bot):
    user_id = message.from_user.id
    password = message.text
    if len(password) < 4 or len(password) > 50:
        await send_message(message.chat.id, "❌ Password must be between 4 and 50 characters!", ParseMode.HTML)
        return
    data = get_data(user_id)
    data["password"] = password
    set_data(user_id, data)
    await delete_messages(message.chat.id, message.message_id)
    await send_message(
        message.chat.id,
        get_settings_message(data),
        reply_markup=build_main_keyboard(data),
        parse_mode=ParseMode.HTML
    )
    set_state(user_id, "pdf_settings")

@dp.callback_query(lambda c: c.data == "pdf_back_settings")
async def pdf_back_settings(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    data = get_data(user_id)
    set_state(user_id, "pdf_settings")
    await callback.message.edit_text(
        text=get_settings_message(data),
        reply_markup=build_main_keyboard(data),
        parse_mode=ParseMode.HTML
    )
    await callback.answer("Returned To Settings")

@dp.callback_query(lambda c: c.data == "pdf_start_processing")
async def pdf_start_processing(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    data = get_data(user_id)
    data["images"] = []
    set_data(user_id, data)
    set_state(user_id, "collecting_images")

    page_size_text = "A4" if data["page_size"] == "a4" else "AUTO"
    page_nums_text = "No" if not data["page_numbers"] else "Yes"
    watermark_text = "No" if not data["watermark"] else "Yes"

    text = (
        f"<b>📸 Ready to collect images!</b>\n\n"
        f"<b>Title:</b> {data['title']}\n"
        f"<b>Page size:</b> {page_size_text}\n"
        f"<b>DPI:</b> {data['dpi']}\n"
        f"<b>Fit mode:</b> {data['fit_mode'].capitalize()}\n"
        f"<b>Page numbers:</b> {page_nums_text}\n"
        f"<b>Watermarks :</b> {watermark_text}\n"
        f"<b>Images :</b> 0/100\n"
        "Send me images now!"
    )

    await callback.message.edit_text(text, reply_markup=build_collection_keyboard(0), parse_mode=ParseMode.HTML)
    user_data[user_id]["msg_id"] = callback.message.message_id
    await callback.answer("Ready To Collect Images!")

@dp.message(lambda m: get_state(m.from_user.id) == "collecting_images" and m.photo)
@new_task
@SmartDefender
async def collect_image(message: Message, bot: Bot):
    user_id = message.from_user.id
    data = get_data(user_id)

    if len(data["images"]) >= 100:
        await send_message(message.chat.id, "❌ Maximum 100 images allowed!", ParseMode.HTML)
        return

    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    img_bytes = await bot.download_file(file.file_path)
    data["images"].append(img_bytes.read())
    set_data(user_id, data)

    count = len(data["images"])
    page_size_text = "A4" if data["page_size"] == "a4" else "AUTO"
    page_nums_text = "No" if not data["page_numbers"] else "Yes"
    watermark_text = "No" if not data["watermark"] else "Yes"

    text = (
        f"<b>📸 Ready to collect images!</b>\n\n"
        f"<b>Title:</b> {data['title']}\n"
        f"<b>Page size:</b> {page_size_text}\n"
        f"<b>DPI:</b> {data['dpi']}\n"
        f"<b>Fit mode:</b> {data['fit_mode'].capitalize()}\n"
        f"<b>Page numbers:</b> {page_nums_text}\n"
        f"<b>Watermarks :</b> {watermark_text}\n"
        f"<b>Images :</b> {count}/100\n"
        "Send me images now!"
    )

    await bot.edit_message_text(
        text=text,
        chat_id=message.chat.id,
        message_id=data["msg_id"],
        reply_markup=build_collection_keyboard(count),
        parse_mode=ParseMode.HTML
    )

@dp.callback_query(lambda c: c.data == "pdf_generate")
async def pdf_generate(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    data = get_data(user_id)
    if not data["images"]:
        await callback.answer("❌ No images to generate PDF!", show_alert=True)
        return

    await callback.message.delete()
    proc_msg = await send_message(callback.message.chat.id, "<b>⏳ Processing Your Document...</b>", ParseMode.HTML)
    start = time.time()
    temp_path = None

    try:
        temp_path = await asyncio.get_event_loop().run_in_executor(None, generate_pdf_sync, data)
        await proc_msg.edit_text("<b>📤 Uploading......</b>")

        size = os.path.getsize(temp_path)
        size_text = f"{size/1024:.2f} KB" if size < 1024*1024 else f"{size/(1024*1024):.2f} MB"
        time_taken = f"{time.time() - start:.2f}s"
        filename = f"{data['title']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"

        caption = (
            f"<b>🔍 Successfully Generated PDF 📋</b><b>┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉</b>\n"
            f"<b> Name:</b> {filename}\n"
            f"<b> Size: {size_text} </b>\n"
            f"<b>Time  Taken: </b> {time_taken}\n"
            f"<b>DPI:</b> {data['dpi']}\n"
            f"<b>┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉</b>\n"
            f"<b> Fit mode:</b> {data['fit_mode'].capitalize()}\n"
            f"<b> Page numbers: </b> {'Yes' if data['page_numbers'] else 'No'}\n"
            f"<b>Watermarks :</b> {'Yes' if data['watermark'] else 'No'}\n"
            f"<b>Images :</b> {len(data['images'])}/100\n"
            f"<b>┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉┉</b>\n"
            f"<b>🔍Thanks For Using Smart Tool 🤖</b>"
        )

        await bot.send_document(
            chat_id=callback.message.chat.id,
            document=FSInputFile(temp_path, filename=filename),
            caption=caption,
            parse_mode=ParseMode.HTML
        )
        await proc_msg.delete()

    except Exception as e:
        await proc_msg.edit_text(f"❌ Error generating PDF: {str(e)}")
    finally:
        if temp_path and os.path.exists(temp_path):
            clean_download(temp_path)

    clear_state(user_id)

def generate_pdf_sync(data: dict) -> str:
    fd, temp_path = tempfile.mkstemp(suffix='.pdf')
    os.close(fd)

    try:
        if data["page_size"] == "a4":
            page_width, page_height = A4
        else:
            first_img = Image.open(BytesIO(data["images"][0]))
            aspect = first_img.width / first_img.height
            page_width = 595
            page_height = page_width / aspect

        c = canvas.Canvas(temp_path, pagesize=(page_width, page_height))

        for idx, img_data in enumerate(data["images"], 1):
            img = Image.open(BytesIO(img_data))

            if data["watermark"]:
                draw = ImageDraw.Draw(img)
                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 60)
                except:
                    try:
                        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 60)
                    except:
                        font = ImageFont.load_default()

                bbox = draw.textbbox((0, 0), data["watermark"], font=font)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]

                watermark_img = Image.new('RGBA', (text_width + 40, text_height + 40), (255, 255, 255, 0))
                watermark_draw = ImageDraw.Draw(watermark_img)
                watermark_draw.text((20, 20), data["watermark"], font=font, fill=(128, 128, 128, 128))

                watermark_img = watermark_img.rotate(45, expand=True)

                position = ((img.width - watermark_img.width) // 2, (img.height - watermark_img.height) // 2)

                if img.mode != 'RGBA':
                    img = img.convert('RGBA')

                img.paste(watermark_img, position, watermark_img)
                img = img.convert('RGB')

            img_buffer = BytesIO()
            img.save(img_buffer, format='JPEG', dpi=(data["dpi"], data["dpi"]))
            img_buffer.seek(0)

            img_reader = ImageReader(img_buffer)
            img_width_points = img.width * 72 / data["dpi"]
            img_height_points = img.height * 72 / data["dpi"]

            if data["fit_mode"] == "shrink":
                if img_width_points > page_width or img_height_points > page_height:
                    ratio = min(page_width / img_width_points, page_height / img_height_points)
                    img_width_points *= ratio
                    img_height_points *= ratio
            else:
                ratio = max(page_width / img_width_points, page_height / img_height_points)
                img_width_points *= ratio
                img_height_points *= ratio

            x_pos = (page_width - img_width_points) / 2
            y_pos = (page_height - img_height_points) / 2

            c.drawImage(img_reader, x_pos, y_pos, width=img_width_points, height=img_height_points)

            if data["page_numbers"]:
                c.setFont("Helvetica", 10)
                page_num_text = f"{idx}"

                position = data["page_numbers"]

                if "top" in position:
                    y = page_height - 20
                else:
                    y = 20

                if "left" in position:
                    x = 20
                elif "right" in position:
                    x = page_width - 40
                else:
                    x = page_width / 2 - 10

                c.drawString(x, y, page_num_text)

            c.showPage()

        c.save()

        if data["cover_page"]:
            cover_fd, cover_path = tempfile.mkstemp(suffix='.pdf')
            os.close(cover_fd)

            try:
                cover_canvas = canvas.Canvas(cover_path, pagesize=(page_width, page_height))

                cover_canvas.setFont("Helvetica-Bold", 48)
                title_text = data["title"]
                text_width = cover_canvas.stringWidth(title_text, "Helvetica-Bold", 48)
                cover_canvas.drawString((page_width - text_width) / 2, page_height / 2, title_text)

                cover_canvas.setFont("Helvetica", 16)
                date_text = datetime.now().strftime("%B %d, %Y")
                date_width = cover_canvas.stringWidth(date_text, "Helvetica", 16)
                cover_canvas.drawString((page_width - date_width) / 2, page_height / 2 - 60, date_text)

                if data["cover_page"] == "bold":
                    cover_canvas.setFillColorRGB(0.2, 0.2, 0.2)
                    cover_canvas.rect(50, page_height / 2 - 100, page_width - 100, 200, fill=1)
                    cover_canvas.setFillColorRGB(1, 1, 1)
                    cover_canvas.drawString((page_width - text_width) / 2, page_height / 2, title_text)
                elif data["cover_page"] == "minimal":
                    cover_canvas.setStrokeColorRGB(0.5, 0.5, 0.5)
                    cover_canvas.setLineWidth(2)
                    cover_canvas.line(100, page_height / 2 - 80, page_width - 100, page_height / 2 - 80)

                cover_canvas.save()

                final_fd, final_path = tempfile.mkstemp(suffix='.pdf')
                os.close(final_fd)

                writer = PdfWriter()

                with open(cover_path, 'rb') as cover_file:
                    cover_reader = PdfReader(cover_file)
                    writer.add_page(cover_reader.pages[0])

                with open(temp_path, 'rb') as content_file:
                    content_reader = PdfReader(content_file)
                    for page in content_reader.pages:
                        writer.add_page(page)

                if data["password"]:
                    writer.encrypt(data["password"])

                with open(final_path, 'wb') as output_file:
                    writer.write(output_file)

                os.unlink(cover_path)
                os.unlink(temp_path)

                return final_path

            except Exception as e:
                if os.path.exists(cover_path):
                    os.unlink(cover_path)
                raise e

        elif data["password"]:
            protected_fd, protected_path = tempfile.mkstemp(suffix='.pdf')
            os.close(protected_fd)

            try:
                writer = PdfWriter()

                with open(temp_path, 'rb') as input_file:
                    reader = PdfReader(input_file)
                    for page in reader.pages:
                        writer.add_page(page)

                writer.encrypt(data["password"])

                with open(protected_path, 'wb') as output_file:
                    writer.write(output_file)

                os.unlink(temp_path)

                return protected_path

            except Exception as e:
                if os.path.exists(protected_path):
                    os.unlink(protected_path)
                raise e

        return temp_path

    except Exception as e:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
        raise e