import io
import os
from typing import Dict
import qrcode
from qrcode import ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q, ERROR_CORRECT_H
from qrcode.image.styles.moduledrawers import (
    SquareModuleDrawer,
    RoundedModuleDrawer,
    CircleModuleDrawer,
)
from PIL import Image, ImageDraw, ImageFont
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.enums import ParseMode, ChatType
from bot import dp
from bot.helpers.botutils import send_message, delete_messages
from bot.helpers.commands import BotCommands
from bot.helpers.buttons import SmartButtons
from bot.helpers.logger import LOGGER
from bot.helpers.utils import new_task, clean_download
from bot.helpers.notify import Smart_Notify
from bot.helpers.defend import SmartDefender

user_states: Dict[int, Dict] = {}
user_data: Dict[int, Dict] = {}

SIZES = {"small": 10, "medium": 15, "large": 20, "xlarge": 25}
ERROR_LEVELS = {"low": ERROR_CORRECT_L, "medium": ERROR_CORRECT_M, "high": ERROR_CORRECT_Q, "max": ERROR_CORRECT_H}
STYLES = {
    "classic": {"drawer": SquareModuleDrawer(), "color": (0, 0, 0)},
    "blue": {"drawer": SquareModuleDrawer(), "color": (0, 0, 255)},
    "gradient": {"drawer": RoundedModuleDrawer(), "color": (100, 0, 200)},
    "dark": {"drawer": SquareModuleDrawer(), "color": (30, 30, 30)},
    "green": {"drawer": CircleModuleDrawer(), "color": (0, 128, 0)},
}
LOGO_SHAPES = {"square": "⬜ Square", "circle": "⭕ Circle", "rounded": "⏹ Rounded"}


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


def get_initial_message() -> str:
    return (
        "<b>📱 QR Code Generator</b>\n"
        "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        "Send me the data you'd like to convert into a QR code.\n\n"
        "<b>✅ Supported Formats:</b>\n"
        "• Plain text\n"
        "• Website URLs → <code>https://example.com</code>\n"
        "• Phone numbers → <code>tel:+1234567890</code>\n"
        "• Email addresses → <code>mailto:email@example.com</code>\n"
        "• WiFi credentials → <code>WIFI:T:WPA;S:NetworkName;P:Password;;</code>\n"
        "• SMS messages → <code>smsto:+1234567890:Your message</code>\n"
        "• vCard contact info\n\n"
        "<b>🔢 Max Length:</b> <code>2953 characters</code>"
    )

def get_settings_message(data: Dict) -> str:
    size_map = {"small": "📄 Small", "medium": "📄 Medium", "large": "📄 Large", "xlarge": "📄 Extra Large"}
    err_map = {"low": "L (7%)", "medium": "M (15%)", "high": "H (30%)", "max": "Q (25%)"}
    style_map = {"classic": "⬛ Classic", "blue": "🔵 Blue", "gradient": "🌈 Gradient", "dark": "⚫ Dark", "green": "🟢 Green"}

    size_text = size_map[data["size"]]
    err_text = err_map[data["error"]]
    style_text = style_map[data["style"]]

    logo_part = f"<b>Logo:</b> <code>{data['logo_shape']}</code>\n" if data.get("has_logo") else ""
    label_part = f"<b>Label:</b> <code>{data['label']}</code>\n" if data.get("label") else ""

    return (
        "<b>⚙️ QR Code Settings</b>\n\n"
        f"<b>Data:</b> <code>{data['text'][:50]}{'...' if len(data['text']) > 50 else ''}</code>\n"
        f"<b>Size:</b> <code>{size_text}</code>\n"
        f"<b>Error Correction:</b> <code>{err_text}</code>\n"
        f"<b>Style:</b> <code>{style_text}</code>\n"
        f"{logo_part}{label_part}\n"
        "<b>Configure your QR code and click 'Generate'!</b>"
    )


def build_settings_keyboard(data: Dict):
    buttons = SmartButtons()
    
    size_buttons = [
        ("small", "📱 Small"),
        ("medium", "📄 Medium"),
        ("large", "🖼️ Large"),
        ("xlarge", "🎯 Extra Large")
    ]
    
    err_buttons = [
        ("low", "⚡ Low"),
        ("medium", "⚖️ Medium"),
        ("high", "🛡️High"),
        ("max", "💎 Max")
    ]
    
    text = f"✅ {size_buttons[0][1].split()[1]}" if size_buttons[0][0] == data["size"] else size_buttons[0][1]
    buttons.button(text, f"qr_size_{size_buttons[0][0]}")
    text = f"✅ {size_buttons[1][1].split()[1]}" if size_buttons[1][0] == data["size"] else size_buttons[1][1]
    buttons.button(text, f"qr_size_{size_buttons[1][0]}")
    
    text = f"✅ {size_buttons[2][1].split()[1]}" if size_buttons[2][0] == data["size"] else size_buttons[2][1]
    buttons.button(text, f"qr_size_{size_buttons[2][0]}")
    text = f"✅ {size_buttons[3][1].split()[1]}" if size_buttons[3][0] == data["size"] else size_buttons[3][1]
    buttons.button(text, f"qr_size_{size_buttons[3][0]}")
    
    text = f"✅ {err_buttons[0][1].split()[1]}" if err_buttons[0][0] == data["error"] else err_buttons[0][1]
    buttons.button(text, f"qr_error_{err_buttons[0][0]}")
    text = f"✅ {err_buttons[1][1].split()[1]}" if err_buttons[1][0] == data["error"] else err_buttons[1][1]
    buttons.button(text, f"qr_error_{err_buttons[1][0]}")
    
    text = f"✅ {err_buttons[2][1].split()[1]}" if err_buttons[2][0] == data["error"] else err_buttons[2][1]
    buttons.button(text, f"qr_error_{err_buttons[2][0]}")
    text = f"✅ {err_buttons[3][1].split()[1]}" if err_buttons[3][0] == data["error"] else err_buttons[3][1]
    buttons.button(text, f"qr_error_{err_buttons[3][0]}")
    
    buttons.button("🧠 Change Style", "qr_change_style")
    buttons.button("", "qr_dummy")
    
    logo_text = "✅ Logo Added" if data.get("has_logo") else "🖼️ Add Logo"
    buttons.button(logo_text, "qr_add_logo")
    label_text = "✅ Label Added" if data.get("label") else "🏷 Add Label"
    buttons.button(label_text, "qr_add_label")
    
    buttons.button("💥 Generate QR Code", "qr_generate", position="footer")
    
    return buttons.build_menu(b_cols=2, f_cols=1)


def build_style_keyboard(data: Dict):
    buttons = SmartButtons()
    style_options = [
        ("classic", "⬛ Classic"),
        ("blue", "🔵 Blue"),
        ("gradient", "🌈 Gradient"),
        ("dark", "⚫ Dark"),
        ("green", "🟢 Green")
    ]

    for key, label in style_options[:2]:
        text = f"✅ {label.split()[1]}" if key == data["style"] else label
        buttons.button(text, f"qr_style_{key}")

    for key, label in style_options[2:4]:
        text = f"✅ {label.split()[1]}" if key == data["style"] else label
        buttons.button(text, f"qr_style_{key}")

    key, label = style_options[4]
    text = f"✅ {label.split()[1]}" if key == data["style"] else label
    buttons.button(text, f"qr_style_{key}")

    buttons.button("⬅️ Back To Settings", "qr_back_settings", position="footer")

    return buttons.build_menu(b_cols=2, f_cols=1)


def build_logo_shape_keyboard():
    buttons = SmartButtons()

    buttons.button("⬜️ Square", "qr_logo_square")
    buttons.button("⭕️ Circle", "qr_logo_circle")

    buttons.button("⏹ Rounded", "qr_logo_rounded")

    buttons.button("◀️ Back To Settings", "qr_back_settings", position="footer")

    return buttons.build_menu(b_cols=2, f_cols=1)


def build_logo_upload_keyboard():
    buttons = SmartButtons()

    buttons.button("✅ Choose Shape", "qr_choose_logo_shape")

    buttons.button("🔍 Skip Logo", "qr_skip_logo")

    return buttons.build_menu(b_cols=1)


def build_logo_photo_keyboard():
    buttons = SmartButtons()
    buttons.button("◀️ Skip Logo", "qr_skip_logo")
    return buttons.build_menu(b_cols=1)


def build_label_keyboard():
    buttons = SmartButtons()
    buttons.button("◀️ Skip Label", "qr_skip_label")
    return buttons.build_menu(b_cols=1)


def build_initial_keyboard():
    buttons = SmartButtons()
    buttons.button("❌ Cancel", "qr_cancel")
    return buttons.build_menu(b_cols=1)


@dp.message(Command(commands=["qr", "qrcode"], prefix=BotCommands))
@new_task
@SmartDefender
async def qr_handler(message: Message, bot: Bot):
    user_id = message.from_user.id

    if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        await send_message(
            chat_id=message.chat.id,
            text="<b>⚠️ QR Code can only be created in private chat.</b>",
            parse_mode=ParseMode.HTML
        )
        LOGGER.info(f"User {user_id} tried to use /qr in group chat")
        return

    LOGGER.info(f"User {user_id} started /qr command")

    try:
        await send_message(
            chat_id=message.chat.id,
            text=get_initial_message(),
            reply_markup=build_initial_keyboard(),
            parse_mode=ParseMode.HTML
        )
        set_state(user_id, "waiting_data")
        LOGGER.info(f"QR prompt sent to user {user_id}")
    except Exception as e:
        await Smart_Notify(bot, "qr_handler", e, message)
        LOGGER.error(f"Failed to start QR handler for user {user_id}: {e}")
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Failed to start QR code generator!</b>",
            parse_mode=ParseMode.HTML
        )

@dp.callback_query(lambda c: c.data == 'qr_cancel')
async def cancel_callback(callback_query: CallbackQuery, bot: Bot):
    try:
        user_id = callback_query.from_user.id
        clear_state(user_id)
        await callback_query.message.edit_text(
            text="<b>❌ QR Code Generation Process Cancelled</b>",
            parse_mode=ParseMode.HTML
        )
        await callback_query.answer()
        LOGGER.info(f"User {user_id} cancelled QR code generation")
    except Exception as e:
        await Smart_Notify(bot, "cancel_callback", e)
        await callback_query.answer("Session Expired Please Try Again", show_alert=True)
        LOGGER.error(f"Error in cancel_callback: {e}")
        
@dp.message(lambda message: message.chat.type == ChatType.PRIVATE and not message.from_user.is_bot and message.text and not message.text.startswith(tuple(BotCommands)) and message.from_user.id in user_states and get_state(message.from_user.id) in ["waiting_data", "add_label"])
@new_task
@SmartDefender
async def message_handler(message: Message, bot: Bot):
    user_id = message.from_user.id
    state = get_state(user_id)

    try:
        if state == "waiting_data":
            text = message.text.strip()
            sender = message.from_user
            full_name = sender.first_name or "User"

            LOGGER.info(f"Processing {full_name}'s QR input")

            if len(text) > 2953:
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Text too long! Max 2953 characters.</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.warning(f"Text too long: {len(text)} from user {user_id}")
                return
            if not text:
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>⚠️ Please send valid data.</b>",
                    parse_mode=ParseMode.HTML
                )
                return

            LOGGER.info(f"Validating QR data from user {user_id}")

            data = {
                "text": text,
                "size": "medium",
                "error": "medium",
                "style": "classic",
                "has_logo": False,
                "logo_shape": None,
                "logo_image": None,
                "label": None,
            }
            set_data(user_id, data)
            set_state(user_id, "qr_settings")

            await send_message(
                chat_id=message.chat.id,
                text=get_settings_message(data),
                reply_markup=build_settings_keyboard(data),
                parse_mode=ParseMode.HTML
            )
            await delete_messages(message.chat.id, message.message_id)
            LOGGER.info(f"QR data received from user {user_id}")

        elif state == "add_label":
            label = message.text.strip()
            if len(label) > 100:
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Label too long! Max 100 characters.</b>",
                    parse_mode=ParseMode.HTML
                )
                return

            data = get_data(user_id)
            data["label"] = label
            set_data(user_id, data)
            set_state(user_id, "qr_settings")

            logo_part = f"<b>✅ Logo uploaded!</b>\n<b>Shape:</b> <code>{data['logo_shape']}</code>\n\n" if data.get("has_logo") else ""
            msg_text = (
                f"{logo_part}"
                f"<b>✅ Label added!</b>\n\n"
                f"<b>⚙️ QR Code Settings</b>\n\n"
                "<b>Ready to generate!</b>"
            )

            await send_message(
                chat_id=message.chat.id,
                text=msg_text,
                reply_markup=build_settings_keyboard(data),
                parse_mode=ParseMode.HTML
            )
            await delete_messages(message.chat.id, message.message_id)
            LOGGER.info(f"Label added by user {user_id}: {label}")
    except Exception as e:
        await Smart_Notify(bot, "message_handler", e, message)
        LOGGER.error(f"Error in message_handler for user {user_id}: {e}")
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Failed to process your message!</b>",
            parse_mode=ParseMode.HTML
        )


@dp.message(lambda message: message.chat.type == ChatType.PRIVATE and not message.from_user.is_bot and message.photo and message.from_user.id in user_states and get_state(message.from_user.id) == "waiting_logo_photo")
@new_task
@SmartDefender
async def photo_handler(message: Message, bot: Bot):
    user_id = message.from_user.id
    state = get_state(user_id)

    try:
        if state == "waiting_logo_photo":
            if message.photo:
                photo = message.photo[-1]
                file = await bot.get_file(photo.file_id)
                photo_bytes = await bot.download_file(file.file_path)
                img = Image.open(photo_bytes)

                data = get_data(user_id)
                data["has_logo"] = True
                data["logo_image"] = img
                set_data(user_id, data)
                set_state(user_id, "qr_settings")

                msg_text = (
                    f"<b>✅ Logo uploaded!</b>\n"
                    f"<b>Shape:</b> <code>{data['logo_shape']}</code>\n\n"
                    f"<b>⚙️ QR Code Settings</b>\n\n"
                    "<b>Ready to generate!</b>"
                )

                await send_message(
                    chat_id=message.chat.id,
                    text=msg_text,
                    reply_markup=build_settings_keyboard(data),
                    parse_mode=ParseMode.HTML
                )
                await delete_messages(message.chat.id, message.message_id)
                LOGGER.info(f"Logo uploaded by user {user_id}")
    except Exception as e:
        await Smart_Notify(bot, "photo_handler", e, message)
        LOGGER.error(f"Error in photo_handler for user {user_id}: {e}")
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Failed to process your photo!</b>",
            parse_mode=ParseMode.HTML
        )


@dp.callback_query(lambda c: c.data.startswith('qr_size_'))
async def size_callback(callback_query: CallbackQuery, bot: Bot):
    try:
        user_id = callback_query.from_user.id
        state = get_state(user_id)

        if state != "qr_settings":
            await callback_query.answer("Session Expired Please Try Again", show_alert=True)
            return

        size = callback_query.data.split("_")[2]
        data = get_data(user_id)

        size_names = {"small": "Small", "medium": "Medium", "large": "Large", "xlarge": "Extra Large"}

        if data["size"] == size:
            await callback_query.answer(f"You Already Chosen {size_names[size]} As Size 🙄", show_alert=True)
            return

        data["size"] = size
        set_data(user_id, data)
        await callback_query.message.edit_text(
            text=get_settings_message(data),
            reply_markup=build_settings_keyboard(data),
            parse_mode=ParseMode.HTML
        )
        await callback_query.answer(f"QR Code Size Updated To {size_names[size]} Size")
        LOGGER.info(f"User {user_id} changed size to {size}")
    except Exception as e:
        await Smart_Notify(bot, "size_callback", e)
        await callback_query.answer("Session Expired Please Try Again", show_alert=True)
        LOGGER.error(f"Error in size_callback: {e}")


@dp.callback_query(lambda c: c.data.startswith('qr_error_'))
async def error_callback(callback_query: CallbackQuery, bot: Bot):
    try:
        user_id = callback_query.from_user.id
        state = get_state(user_id)

        if state != "qr_settings":
            await callback_query.answer("Session Expired Please Try Again", show_alert=True)
            return

        error = callback_query.data.split("_")[2]
        data = get_data(user_id)

        error_percent = {"low": "7", "medium": "15", "high": "30", "max": "25"}
        error_names = {"low": "Low", "medium": "Medium", "high": "High", "max": "Max"}

        if data["error"] == error:
            await callback_query.answer(f"You Already Chosen {error_names[error]} As Error Correction 🙄", show_alert=True)
            return

        data["error"] = error
        set_data(user_id, data)
        await callback_query.message.edit_text(
            text=get_settings_message(data),
            reply_markup=build_settings_keyboard(data),
            parse_mode=ParseMode.HTML
        )
        await callback_query.answer(f"Error Correction Updated To {error_percent[error]} Percent")
        LOGGER.info(f"User {user_id} changed error correction to {error}")
    except Exception as e:
        await Smart_Notify(bot, "error_callback", e)
        await callback_query.answer("Session Expired Please Try Again", show_alert=True)
        LOGGER.error(f"Error in error_callback: {e}")


@dp.callback_query(lambda c: c.data == 'qr_change_style')
async def change_style_callback(callback_query: CallbackQuery, bot: Bot):
    try:
        user_id = callback_query.from_user.id
        state = get_state(user_id)

        if state != "qr_settings":
            await callback_query.answer("Session Expired Please Try Again", show_alert=True)
            return

        data = get_data(user_id)
        set_state(user_id, "qr_choose_style")
        await callback_query.message.edit_text(
            text="<b>🎨 Select QR Code Style</b>\n\n<b>Choose a color scheme for your QR code:</b>",
            reply_markup=build_style_keyboard(data),
            parse_mode=ParseMode.HTML
        )
        await callback_query.answer()
        LOGGER.info(f"User {user_id} opened style menu")
    except Exception as e:
        await Smart_Notify(bot, "change_style_callback", e)
        await callback_query.answer("Session Expired Please Try Again", show_alert=True)
        LOGGER.error(f"Error in change_style_callback: {e}")


@dp.callback_query(lambda c: c.data.startswith('qr_style_'))
async def style_callback(callback_query: CallbackQuery, bot: Bot):
    try:
        user_id = callback_query.from_user.id
        state = get_state(user_id)

        if state != "qr_choose_style":
            await callback_query.answer("Session Expired Please Try Again", show_alert=True)
            return

        style = callback_query.data.split("_")[2]
        data = get_data(user_id)
        data["style"] = style
        set_data(user_id, data)
        set_state(user_id, "qr_settings")
        await callback_query.message.edit_text(
            text=get_settings_message(data),
            reply_markup=build_settings_keyboard(data),
            parse_mode=ParseMode.HTML
        )
        await callback_query.answer()
        LOGGER.info(f"User {user_id} changed style to {style}")
    except Exception as e:
        await Smart_Notify(bot, "style_callback", e)
        await callback_query.answer("Session Expired Please Try Again", show_alert=True)
        LOGGER.error(f"Error in style_callback: {e}")


@dp.callback_query(lambda c: c.data == 'qr_back_settings')
async def back_settings_callback(callback_query: CallbackQuery, bot: Bot):
    try:
        user_id = callback_query.from_user.id
        data = get_data(user_id)
        set_state(user_id, "qr_settings")
        await callback_query.message.edit_text(
            text=get_settings_message(data),
            reply_markup=build_settings_keyboard(data),
            parse_mode=ParseMode.HTML
        )
        await callback_query.answer()
        LOGGER.info(f"User {user_id} returned to settings")
    except Exception as e:
        await Smart_Notify(bot, "back_settings_callback", e)
        await callback_query.answer("Session Expired Please Try Again", show_alert=True)
        LOGGER.error(f"Error in back_settings_callback: {e}")


@dp.callback_query(lambda c: c.data == 'qr_add_logo')
async def add_logo_callback(callback_query: CallbackQuery, bot: Bot):
    try:
        user_id = callback_query.from_user.id
        state = get_state(user_id)

        if state != "qr_settings":
            await callback_query.answer("Session Expired Please Try Again", show_alert=True)
            return

        await callback_query.message.edit_text(
            text=(
                "<b>🖼️ Upload Logo Image</b>\n\n"
                "Send me an image to use as logo in QR code center.\n\n"
                "<b>✅ Best practices:</b>\n"
                "<code>• Use square or circular logos</code>\n"
                "<code>• High contrast with background</code>\n"
                "<code>• Simple designs work best</code>\n"
                "<code>• PNG with transparency recommended</code>\n"
                "<code>• Logo will be 25% of QR code size</code>\n\n"
                "<b>Choose shape or skip to continue without logo.</b>"
            ),
            reply_markup=build_logo_upload_keyboard(),
            parse_mode=ParseMode.HTML
        )
        set_state(user_id, "qr_upload_logo")
        await callback_query.answer()
        LOGGER.info(f"User {user_id} started logo upload")
    except Exception as e:
        await Smart_Notify(bot, "add_logo_callback", e)
        await callback_query.answer("Session Expired Please Try Again", show_alert=True)
        LOGGER.error(f"Error in add_logo_callback: {e}")


@dp.callback_query(lambda c: c.data == 'qr_choose_logo_shape')
async def choose_logo_shape_callback(callback_query: CallbackQuery, bot: Bot):
    try:
        user_id = callback_query.from_user.id
        state = get_state(user_id)

        if state != "qr_upload_logo":
            await callback_query.answer("Session Expired Please Try Again", show_alert=True)
            return

        set_state(user_id, "qr_choose_logo_shape")
        await callback_query.message.edit_text(
            text="<b>🔲 Select Logo Shape</b>\n\n<b>Choose how your logo should appear:</b>",
            reply_markup=build_logo_shape_keyboard(),
            parse_mode=ParseMode.HTML
        )
        await callback_query.answer()
        LOGGER.info(f"User {user_id} opened logo shape menu")
    except Exception as e:
        await Smart_Notify(bot, "choose_logo_shape_callback", e)
        await callback_query.answer("Session Expired Please Try Again", show_alert=True)
        LOGGER.error(f"Error in choose_logo_shape_callback: {e}")


@dp.callback_query(lambda c: c.data == 'qr_logo_square')
async def logo_square_callback(callback_query: CallbackQuery, bot: Bot):
    try:
        user_id = callback_query.from_user.id
        state = get_state(user_id)

        if state != "qr_choose_logo_shape":
            await callback_query.answer("Session Expired Please Try Again", show_alert=True)
            return

        shape_text = LOGO_SHAPES["square"]
        data = get_data(user_id)
        data["logo_shape"] = shape_text
        set_data(user_id, data)
        set_state(user_id, "waiting_logo_photo")
        await callback_query.message.edit_text(
            text=f"<b>🖼️ Upload Logo Image</b>\n\n<b>Selected shape:</b> <code>{shape_text}</code>\n\n<b>Now send me the logo image.</b>",
            reply_markup=build_logo_photo_keyboard(),
            parse_mode=ParseMode.HTML
        )
        await callback_query.answer()
        LOGGER.info(f"User {user_id} selected square logo shape")
    except Exception as e:
        await Smart_Notify(bot, "logo_square_callback", e)
        await callback_query.answer("Session Expired Please Try Again", show_alert=True)
        LOGGER.error(f"Error in logo_square_callback: {e}")


@dp.callback_query(lambda c: c.data == 'qr_logo_circle')
async def logo_circle_callback(callback_query: CallbackQuery, bot: Bot):
    try:
        user_id = callback_query.from_user.id
        state = get_state(user_id)

        if state != "qr_choose_logo_shape":
            await callback_query.answer("Session Expired Please Try Again", show_alert=True)
            return

        shape_text = LOGO_SHAPES["circle"]
        data = get_data(user_id)
        data["logo_shape"] = shape_text
        set_data(user_id, data)
        set_state(user_id, "waiting_logo_photo")
        await callback_query.message.edit_text(
            text=f"<b>🖼️ Upload Logo Image</b>\n\n<b>Selected shape:</b> <code>{shape_text}</code>\n\n<b>Now send me the logo image.</b>",
            reply_markup=build_logo_photo_keyboard(),
            parse_mode=ParseMode.HTML
        )
        await callback_query.answer()
        LOGGER.info(f"User {user_id} selected circle logo shape")
    except Exception as e:
        await Smart_Notify(bot, "logo_circle_callback", e)
        await callback_query.answer("Session Expired Please Try Again", show_alert=True)
        LOGGER.error(f"Error in logo_circle_callback: {e}")


@dp.callback_query(lambda c: c.data == 'qr_logo_rounded')
async def logo_rounded_callback(callback_query: CallbackQuery, bot: Bot):
    try:
        user_id = callback_query.from_user.id
        state = get_state(user_id)

        if state != "qr_choose_logo_shape":
            await callback_query.answer("Session Expired Please Try Again", show_alert=True)
            return

        shape_text = LOGO_SHAPES["rounded"]
        data = get_data(user_id)
        data["logo_shape"] = shape_text
        set_data(user_id, data)
        set_state(user_id, "waiting_logo_photo")
        await callback_query.message.edit_text(
            text=f"<b>🖼️ Upload Logo Image</b>\n\n<b>Selected shape:</b> <code>{shape_text}</code>\n\n<b>Now send me the logo image.</b>",
            reply_markup=build_logo_photo_keyboard(),
            parse_mode=ParseMode.HTML
        )
        await callback_query.answer()
        LOGGER.info(f"User {user_id} selected rounded logo shape")
    except Exception as e:
        await Smart_Notify(bot, "logo_rounded_callback", e)
        await callback_query.answer("Session Expired Please Try Again", show_alert=True)
        LOGGER.error(f"Error in logo_rounded_callback: {e}")


@dp.callback_query(lambda c: c.data == 'qr_skip_logo')
async def skip_logo_callback(callback_query: CallbackQuery, bot: Bot):
    try:
        user_id = callback_query.from_user.id
        data = get_data(user_id)
        data["has_logo"] = False
        data.pop("logo_shape", None)
        data.pop("logo_image", None)
        set_data(user_id, data)
        set_state(user_id, "qr_settings")
        await callback_query.message.edit_text(
            text=get_settings_message(data),
            reply_markup=build_settings_keyboard(data),
            parse_mode=ParseMode.HTML
        )
        await callback_query.answer()
        LOGGER.info(f"User {user_id} skipped logo")
    except Exception as e:
        await Smart_Notify(bot, "skip_logo_callback", e)
        await callback_query.answer("Session Expired Please Try Again", show_alert=True)
        LOGGER.error(f"Error in skip_logo_callback: {e}")


@dp.callback_query(lambda c: c.data == 'qr_add_label')
async def add_label_callback(callback_query: CallbackQuery, bot: Bot):
    try:
        user_id = callback_query.from_user.id
        state = get_state(user_id)

        if state != "qr_settings":
            await callback_query.answer("Session Expired Please Try Again", show_alert=True)
            return

        set_state(user_id, "add_label")
        await callback_query.message.edit_text(
            text=(
                "<b>🏷️ Label Text</b>\n\n"
                "Send me the text to display below QR code.\n"
                "<b>Example:</b> <code>Scan Me, My Website, etc.</code>\n\n"
                "<b>Click 'Skip Label' to continue without label.</b>"
            ),
            reply_markup=build_label_keyboard(),
            parse_mode=ParseMode.HTML
        )
        await callback_query.answer()
        LOGGER.info(f"User {user_id} started label input")
    except Exception as e:
        await Smart_Notify(bot, "add_label_callback", e)
        await callback_query.answer("Session Expired Please Try Again", show_alert=True)
        LOGGER.error(f"Error in add_label_callback: {e}")


@dp.callback_query(lambda c: c.data == 'qr_skip_label')
async def skip_label_callback(callback_query: CallbackQuery, bot: Bot):
    try:
        user_id = callback_query.from_user.id
        data = get_data(user_id)
        data.pop("label", None)
        set_data(user_id, data)
        set_state(user_id, "qr_settings")
        await callback_query.message.edit_text(
            text=get_settings_message(data),
            reply_markup=build_settings_keyboard(data),
            parse_mode=ParseMode.HTML
        )
        await callback_query.answer()
        LOGGER.info(f"User {user_id} skipped label")
    except Exception as e:
        await Smart_Notify(bot, "skip_label_callback", e)
        await callback_query.answer("Session Expired Please Try Again", show_alert=True)
        LOGGER.error(f"Error in skip_label_callback: {e}")


@dp.callback_query(lambda c: c.data == 'qr_generate')
async def generate_callback(callback_query: CallbackQuery, bot: Bot):
    try:
        user_id = callback_query.from_user.id
        state = get_state(user_id)

        if state != "qr_settings":
            await callback_query.answer("Session Expired Please Try Again", show_alert=True)
            return

        data = get_data(user_id)
        sender = callback_query.from_user
        full_name = sender.first_name or "User"
        temp_path = f"downloads/{user_id}.png"

        os.makedirs("downloads", exist_ok=True)

        LOGGER.info(f"Processing {full_name}'s QR generation")
        LOGGER.info(f"Validating all received data for user {user_id}")

        await callback_query.message.edit_text(
            text="<b>⚙️ Generating Your QR Code...</b>",
            parse_mode=ParseMode.HTML
        )

        qr = qrcode.QRCode(
            version=None,
            error_correction=ERROR_LEVELS[data["error"]],
            box_size=SIZES[data["size"]],
            border=4,
        )
        qr.add_data(data["text"])
        qr.make(fit=True)

        style = STYLES[data["style"]]
        img = qr.make_image(
            fill_color=style["color"],
            back_color=(255, 255, 255),
            module_drawer=style["drawer"],
        )

        img = img.convert("RGB")

        if data.get("has_logo") and data.get("logo_image"):
            logo = data["logo_image"].copy()
            logo_size = img.size[0] // 4
            logo = logo.resize((logo_size, logo_size), Image.LANCZOS)

            if logo.mode != "RGBA":
                logo = logo.convert("RGBA")

            img_with_logo = Image.new("RGB", img.size, (255, 255, 255))
            img_with_logo.paste(img, (0, 0))

            pos = ((img.size[0] - logo.size[0]) // 2, (img.size[1] - logo.size[1]) // 2)

            if logo.mode == "RGBA":
                img_with_logo.paste(logo, pos, logo)
            else:
                img_with_logo.paste(logo, pos)

            img = img_with_logo

        if data.get("label"):
            label_text = data["label"]
            label_height = 100
            new_img = Image.new("RGB", (img.size[0], img.size[1] + label_height), (255, 255, 255))
            new_img.paste(img, (0, 0))

            draw = ImageDraw.Draw(new_img)

            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
            except:
                try:
                    font = ImageFont.truetype("arial.ttf", 40)
                except:
                    font = ImageFont.load_default()

            try:
                bbox = font.getbbox(label_text)
                text_width = bbox[2] - bbox[0]
            except:
                text_width = len(label_text) * 20

            text_x = (new_img.size[0] - text_width) // 2
            text_y = img.size[1] + 30

            draw.text((text_x, text_y), label_text, fill=(0, 0, 0), font=font)
            img = new_img

        LOGGER.info(f"Generating Image -> /{temp_path}")

        img.save(temp_path, format="PNG")

        size_map = {"small": "Small", "medium": "Medium", "large": "Large", "xlarge": "Extra Large"}
        err_map = {"low": "L (7%)", "medium": "M (15%)", "high": "H (30%)", "max": "Q (25%)"}
        style_map = {"classic": "⬛ Classic", "blue": "🔵 Blue", "gradient": "🌈 Gradient", "dark": "⚫ Dark", "green": "🟢 Green"}

        size_text = size_map[data["size"]]
        err_text = err_map[data["error"]]
        style_text = style_map[data["style"]]

        caption = (
            "<b>✅ QR Code Generated</b>\n\n"
            f"<b>Size:</b> <code>📄 {size_text}</code>\n"
            f"<b>Style:</b> <code>{style_text}</code>\n"
            f"<b>Error Correction:</b> <code>{err_text}</code>"
        )

        await callback_query.message.delete()

        photo_file = FSInputFile(temp_path)

        await bot.send_photo(
            chat_id=callback_query.message.chat.id,
            photo=photo_file,
            caption=caption,
            parse_mode=ParseMode.HTML
        )

        clear_state(user_id)
        await callback_query.answer()
        LOGGER.info(f"QR code sent to user {user_id}")

        LOGGER.info(f"Cleaning Download -> /{temp_path}")
        clean_download(temp_path)

    except Exception as e:
        await Smart_Notify(bot, "generate_callback", e)
        await callback_query.answer("Failed to generate QR code!", show_alert=True)
        LOGGER.error(f"Error in generate_callback for user {user_id}: {e}")
        try:
            await send_message(
                chat_id=callback_query.message.chat.id,
                text="<b>❌ Failed to generate QR code!</b>",
                parse_mode=ParseMode.HTML
            )
        except:
            pass