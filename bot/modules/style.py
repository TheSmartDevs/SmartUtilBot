import json
from pathlib import Path
from aiogram import Bot, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ParseMode
from bot import dp
from bot.helpers.utils import new_task
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.buttons import SmartButtons
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.defend import SmartDefender

FONTS_FILE = Path("bot/Assets/fonts.json")
fonts = []
user_original_texts = {}
user_current_pages = {}
user_current_fonts = {}

def load_fonts():
    global fonts
    try:
        if not FONTS_FILE.exists():
            LOGGER.error(f"fonts.json file not found at {FONTS_FILE}")
            LOGGER.error(f"Absolute path checked: {FONTS_FILE.absolute()}")
            raise FileNotFoundError(f"fonts.json missing at {FONTS_FILE}")
        
        with open(FONTS_FILE, "r", encoding="utf-8") as f:
            fonts = json.load(f)
        
        if not fonts or not isinstance(fonts, list):
            LOGGER.error(f"Invalid fonts data: Expected non-empty list, got {type(fonts)}")
            raise ValueError("fonts.json must contain a non-empty list")
        
        LOGGER.info(f"Successfully loaded {len(fonts)} fonts from {FONTS_FILE}")
        return True
        
    except FileNotFoundError as e:
        LOGGER.error(f"Font file not found: {e}")
        LOGGER.error("Please ensure fonts.json exists at bot/Assets/fonts.json")
        return False
    except json.JSONDecodeError as e:
        LOGGER.error(f"Invalid JSON in fonts.json: {e}")
        LOGGER.error(f"Error at line {e.lineno}, column {e.colno}")
        return False
    except ValueError as e:
        LOGGER.error(f"Invalid font data structure: {e}")
        return False
    except Exception as e:
        LOGGER.error(f"Unexpected error loading fonts: {e}")
        LOGGER.error(f"Error type: {type(e).__name__}")
        return False

def convert_text(text: str, font_data: dict) -> str:
    lower = font_data.get("fontLower", "")
    upper = font_data.get("fontUpper", "")
    digits = font_data.get("fontDigits", "")

    lower_map = {}
    upper_map = {}
    digits_map = {}

    if isinstance(lower, list):
        for i in range(min(len(lower), 26)):
            lower_map[chr(97 + i)] = lower[i]
    elif lower:
        for i in range(min(len(lower), 26)):
            lower_map[chr(97 + i)] = lower[i]

    if isinstance(upper, list):
        for i in range(min(len(upper), 26)):
            upper_map[chr(65 + i)] = upper[i]
    elif upper:
        for i in range(min(len(upper), 26)):
            upper_map[chr(65 + i)] = upper[i]

    if isinstance(digits, list):
        for i in range(min(len(digits), 10)):
            digits_map[chr(48 + i)] = digits[i]
    elif digits:
        for i in range(min(len(digits), 10)):
            digits_map[chr(48 + i)] = digits[i]

    result = []
    for char in text:
        if char.islower():
            result.append(lower_map.get(char, char))
        elif char.isupper():
            result.append(upper_map.get(char, char))
        elif char.isdigit():
            result.append(digits_map.get(char, char))
        else:
            result.append(char)
    return "".join(result)

def get_button_text(font_data: dict) -> str:
    font_name = font_data["fontName"]
    return convert_text(font_name, font_data)

def get_keyboard(page: int = 0):
    buttons_per_page = 21
    buttons_per_row = 3
    start = page * buttons_per_page
    end = start + buttons_per_page
    current_fonts = fonts[start:end]

    total_pages = (len(fonts) + buttons_per_page - 1) // buttons_per_page

    buttons = SmartButtons()
    
    for font in current_fonts:
        font_idx = fonts.index(font)
        btn_text = get_button_text(font)
        if not btn_text.strip():
            btn_text = font["fontName"]
        buttons.button(text=btn_text, callback_data=f"font_{font_idx}")

    has_previous = page > 0
    has_next = end < len(fonts)

    if page == 0:
        if has_next:
            buttons.button(text="Next »", callback_data=f"page_{page+1}", position="footer")
        buttons.button(text="Close ❌", callback_data="close_style", position="footer")
    elif page == total_pages - 1:
        buttons.button(text="« Previous", callback_data=f"page_{page-1}", position="footer")
        buttons.button(text="Close ❌", callback_data="close_style", position="footer")
    else:
        buttons.button(text="Next »", callback_data=f"page_{page+1}", position="footer")
        buttons.button(text="« Previous", callback_data=f"page_{page-1}", position="footer")
        buttons.button(text="Close ❌", callback_data="close_style", position="footer")

    return buttons.build_menu(b_cols=buttons_per_row, f_cols=2)

@dp.message(Command(commands=["style"], prefix=BotCommands))
@new_task
@SmartDefender
async def cmd_style(message: Message, bot: Bot):
    LOGGER.info(f"Received /style command from user {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
    
    try:
        if not fonts:
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Font Style Service Unavailable</b>\n\n"
                     "Fonts are not loaded. Please contact the administrator.",
                parse_mode=ParseMode.HTML
            )
            LOGGER.error(f"User {message.from_user.id} tried to use /style but fonts are not loaded")
            return

        args = get_args(message)
        text = None
        
        if message.reply_to_message:
            if args and args[0] == "{}":
                text = message.reply_to_message.text or message.reply_to_message.caption
            elif not args:
                text = message.reply_to_message.text or message.reply_to_message.caption
            else:
                text = " ".join(args)
        else:
            if args:
                text = " ".join(args)
        
        if not text:
            await send_message(
                chat_id=message.chat.id,
                text="<b>💫 Stylize anything:</b> <code>/style Type Here</code>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"User {message.from_user.id} used /style without text")
            return

        if len(text) == 0:
            await send_message(
                chat_id=message.chat.id,
                text="<b>💫 Stylize anything:</b> <code>/style Type Here</code>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"User {message.from_user.id} provided empty text")
            return

        kb = get_keyboard(0)
        sent_message = await send_message(
            chat_id=message.chat.id,
            text=f"<code>{text}</code>",
            reply_markup=kb,
            parse_mode=ParseMode.HTML
        )
        
        if sent_message:
            user_key = f"{message.chat.id}_{sent_message.message_id}"
            user_original_texts[user_key] = text
            user_current_pages[user_key] = 0
            user_current_fonts[user_key] = None
            
            LOGGER.info(f"User {message.from_user.id} requested style menu for text: {text[:50]}{'...' if len(text)>50 else ''}")
    
    except Exception as e:
        LOGGER.error(f"Error in /style command: {e}")
        await Smart_Notify(bot, "style", e, message)
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Sorry, an error occurred while processing your request.</b>",
            parse_mode=ParseMode.HTML
        )

@dp.callback_query(F.data.startswith("page_"))
async def process_pagination(callback: CallbackQuery):
    try:
        page = int(callback.data.split("_")[1])
        user_key = f"{callback.message.chat.id}_{callback.message.message_id}"
        user_current_pages[user_key] = page
        
        kb = get_keyboard(page)
        
        await callback.message.edit_reply_markup(reply_markup=kb)
        await callback.answer(f"📄 Navigated To Page {page + 1}", show_alert=False)
        LOGGER.info(f"User {callback.from_user.id} navigated to page {page}")
    except Exception as e:
        LOGGER.error(f"Error in pagination: {e}")
        await callback.answer("❌ Sorry Bro Failed To Navigate!", show_alert=True)

@dp.callback_query(F.data.startswith("font_"))
async def process_font_selection(callback: CallbackQuery):
    try:
        font_idx = int(callback.data.split("_")[1])
        
        if font_idx < 0 or font_idx >= len(fonts):
            await callback.answer("❌ Invalid Font Selected!", show_alert=True)
            return
        
        font_data = fonts[font_idx]
        font_name = font_data["fontName"]

        user_key = f"{callback.message.chat.id}_{callback.message.message_id}"
        original_text = user_original_texts.get(user_key)
        current_page = user_current_pages.get(user_key, 0)
        current_font_idx = user_current_fonts.get(user_key)
        
        if current_font_idx == font_idx:
            await callback.answer(f"Bro Already Applied {font_name} Style ❌", show_alert=True)
            LOGGER.info(f"User {callback.from_user.id} tried to reapply font '{font_name}'")
            return
        
        if not original_text:
            current_text = callback.message.text or callback.message.caption or ""
            
            if "\n\n<b>Click To Copy 👆</b>" in current_text:
                original_text = current_text.split("\n\n<b>Click To Copy 👆</b>")[0]
            else:
                original_text = current_text
            
            original_text = original_text.replace("<code>", "").replace("</code>", "").strip()
            
            if original_text:
                user_original_texts[user_key] = original_text

        if not original_text:
            await callback.answer("❌ Original text not found!", show_alert=True)
            return

        converted = convert_text(original_text, font_data)

        kb = get_keyboard(current_page)

        new_message_text = f"<code>{converted}</code>\n\n<b>Click To Copy 👆</b>"

        await callback.message.edit_text(
            text=new_message_text,
            reply_markup=kb,
            parse_mode=ParseMode.HTML
        )
        
        user_current_fonts[user_key] = font_idx
        
        await callback.answer(f"✨ {font_name} Style Applied!", show_alert=False)
        LOGGER.info(f"User {callback.from_user.id} switched to font '{font_name}'")
        
    except Exception as e:
        LOGGER.error(f"Error editing message: {e}")
        await callback.answer("❌ Sorry Failed to apply style!", show_alert=True)

@dp.callback_query(F.data == "close_style")
async def process_close(callback: CallbackQuery):
    user_key = f"{callback.message.chat.id}_{callback.message.message_id}"
    
    if user_key in user_original_texts:
        del user_original_texts[user_key]
    if user_key in user_current_pages:
        del user_current_pages[user_key]
    if user_key in user_current_fonts:
        del user_current_fonts[user_key]
    
    try:
        await delete_messages(callback.message.chat.id, callback.message.message_id)
        await callback.answer("👋 Menu Successfully Closed!", show_alert=False)
        LOGGER.info(f"User {callback.from_user.id} closed the style menu")
    except Exception as e:
        LOGGER.error(f"Error deleting message: {e}")
        await callback.answer("❌ Failed to close menu!", show_alert=True)

fonts_loaded = load_fonts()
if fonts_loaded:
    LOGGER.info("✅ Font Style module loaded successfully")
else:
    LOGGER.error("❌ Font Style module loaded with errors - /style command will be unavailable")