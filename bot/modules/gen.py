import re
import os
import random
import asyncio
import pycountry
from aiogram import Bot
from aiogram.filters import Command, BaseFilter
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from bot import dp
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.buttons import SmartButtons
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.utils import new_task, clean_download
from bot.helpers.defend import SmartDefender
from smartbindb import SmartBinDB
from config import CC_GEN_LIMIT, MULTI_CCGEN_LIMIT

smartdb = SmartBinDB()

def is_amex_bin(bin_str):
    clean_bin = bin_str.replace('x', '').replace('X', '')
    if len(clean_bin) >= 2:
        return clean_bin[:2] in ['34', '37']
    return False

def extract_bin_from_text(text):
    if not text:
        return None
    text = text.strip()
    for prefix in BotCommands:
        if text.lower().startswith(f'{prefix}gen'):
            text = text[len(f'{prefix}gen'):].strip()
            break
    digits_x_pattern = r'(?:[0-9xX][a-zA-Z0-9!@#$%^&*()_+\-=\[\]{};:\'",.<>/?\\|]*)+(?:[|:/][\d]{2}|xx|xxx|xxxx]+(?:[|:/][\d]{2,4}|xx|xxx|xxxx]+(?:[|:/][\d]{3,4}|xxx|xxxx]+)?)?)?'
    matches = re.findall(digits_x_pattern, text, re.IGNORECASE)
    if matches:
        for match in matches:
            parts = re.split(r'[|:/]', match)
            bin_part = ''.join(filter(lambda x: x.isdigit() or x in 'xX', parts[0]))
            digits_only = re.sub(r'[^0-9]', '', bin_part)
            if 6 <= len(digits_only) <= 16:
                if len(parts) > 1:
                    full_match = bin_part + '|' + '|'.join(parts[1:])
                    LOGGER.info(f"Extracted BIN with format: {full_match}")
                    return full_match
                LOGGER.info(f"Extracted BIN: {digits_only}")
                return digits_only
    return None

async def get_bin_info(bin: str, bot: Bot, message: Message):
    try:
        result = await smartdb.get_bin_info(bin)
        if result.get("status") == "SUCCESS" and result.get("data") and isinstance(result["data"], list) and len(result["data"]) > 0:
            return result
        else:
            LOGGER.error(f"SmartBinDB returned invalid response: {result}")
            await Smart_Notify(bot, "gen", f"SmartBinDB invalid response: {result}", message)
            await send_message(
                chat_id=message.chat.id,
                text="<b>Invalid or Unknown BIN Provided ❌</b>",
                parse_mode=ParseMode.HTML
            )
            return None
    except Exception as e:
        LOGGER.error(f"Error fetching BIN info from SmartBinDB: {str(e)}")
        error_message = "<b>Invalid or Unknown BIN Provided ❌</b>"
        if "Binary database not found or empty" in str(e):
            error_message = "<b>Binary database not found or corrupted. Please contact support ❌</b>"
        await Smart_Notify(bot, "gen", e, message)
        await send_message(
            chat_id=message.chat.id,
            text=error_message,
            parse_mode=ParseMode.HTML
        )
        return None

def luhn_algorithm(card_number):
    digits = [int(d) for d in str(card_number) if d.isdigit()]
    if not digits or len(digits) < 13:
        return False
    checksum = 0
    for i, digit in enumerate(reversed(digits)):
        if i % 2 == 1:
            doubled = digit * 2
            if doubled > 9:
                doubled = doubled // 10 + doubled % 10
            checksum += doubled
        else:
            checksum += digit
    return checksum % 10 == 0

def calculate_luhn_check_digit(partial_card_number):
    digits = [int(d) for d in str(partial_card_number) if d.isdigit()]
    if not digits:
        return 0
    checksum = 0
    for i, digit in enumerate(reversed(digits)):
        if i % 2 == 0:
            doubled = digit * 2
            if doubled > 9:
                doubled = doubled // 10 + doubled % 10
            checksum += doubled
        else:
            checksum += digit
    check_digit = (10 - (checksum % 10)) % 10
    return check_digit

def generate_credit_card(bin, amount, month=None, year=None, cvv=None):
    cards = []
    is_amex = is_amex_bin(bin)
    target_length = 15 if is_amex else 16
    cvv_length = 4 if is_amex else 3
    bin_digits = re.sub(r'[^0-9]', '', bin)
    if len(bin_digits) >= target_length:
        LOGGER.error(f"BIN too long: {len(bin_digits)} digits for target length {target_length}")
        return []
    for _ in range(amount):
        card_body = bin_digits
        remaining_digits = target_length - len(card_body) - 1
        if remaining_digits < 0:
            LOGGER.error(f"Invalid BIN length for card type")
            continue
        for _ in range(remaining_digits):
            card_body += str(random.randint(0, 9))
        check_digit = calculate_luhn_check_digit(card_body)
        card_number = card_body + str(check_digit)
        if not luhn_algorithm(card_number):
            LOGGER.error(f"Generated invalid card: {card_number}")
            continue
        card_month = month if month is not None else f"{random.randint(1, 12):02d}"
        card_year = year if year is not None else str(random.randint(2025, 2035))
        card_cvv = cvv if cvv is not None else ''.join([str(random.randint(0, 9)) for _ in range(cvv_length)])
        formatted_card = f"{card_number}|{card_month}|{card_year}|{card_cvv}"
        cards.append(formatted_card)
        LOGGER.debug(f"Generated valid card: {formatted_card}")
    return cards

def parse_input(user_input):
    bin = None
    month = None
    year = None
    cvv = None
    amount = 10
    if not user_input:
        return None, None, None, None, None
    if isinstance(user_input, list):
        user_input = ' '.join(user_input)
    input_parts = user_input.strip().split()
    if len(input_parts) > 1 and input_parts[-1].isdigit():
        potential_amount = int(input_parts[-1])
        if 1 <= potential_amount <= MULTI_CCGEN_LIMIT:
            amount = potential_amount
            user_input = ' '.join(input_parts[:-1])
    extracted_bin = extract_bin_from_text(user_input)
    if not extracted_bin:
        return None, None, None, None, None
    parts = re.split(r'[|:/]', extracted_bin)
    bin_part = parts[0] if parts else ""
    digits_only = re.sub(r'[^0-9]', '', bin_part)
    if digits_only:
        if 6 <= len(digits_only) <= 16:
            bin = digits_only
        else:
            return None, None, None, None, None
    else:
        return None, None, None, None, None
    if len(parts) > 1:
        if parts[1].lower() == 'xx':
            month = None
        elif parts[1].isdigit() and len(parts[1]) == 2:
            month_val = int(parts[1])
            if 1 <= month_val <= 12:
                month = f"{month_val:02d}"
    if len(parts) > 2:
        if parts[2].lower() == 'xx':
            year = None
        elif parts[2].isdigit():
            year_str = parts[2]
            if len(year_str) == 2:
                year_int = int(year_str)
                if year_int >= 25:
                    year = f"20{year_str}"
                else:
                    year = f"20{year_str}"
            elif len(year_str) == 4:
                year_int = int(year_str)
                if 2025 <= year_int <= 2099:
                    year = year_str
    if len(parts) > 3 and parts[3]:
        if parts[3].lower() in ['xxx', 'xxxx']:
            cvv = None
        elif parts[3].isdigit():
            cvv = parts[3]
    return bin, month, year, cvv, amount

def generate_custom_cards(bin, amount, month=None, year=None, cvv=None):
    return generate_credit_card(bin, amount, month, year, cvv)

def get_flag(country_code):
    try:
        if not country_code or len(country_code) < 2:
            return "Unknown", ""
        country_code = country_code.upper()
        if country_code in ['US1', 'US2']:
            country_code = 'US'
        country = pycountry.countries.get(alpha_2=country_code)
        if not country:
            return "Unknown", ""
        country_name = country.name
        flag_emoji = chr(0x1F1E6 + ord(country_code[0]) - ord('A')) + chr(0x1F1E6 + ord(country_code[1]) - ord('A'))
        return country_name, flag_emoji
    except Exception:
        return "Unknown", ""

class BinPatternFilter(BaseFilter):
    async def __call__(self, message: Message):
        if not message.reply_to_message:
            return False
        reply_text = message.reply_to_message.text or message.reply_to_message.caption
        if not reply_text:
            return False
        gen_command_found = False
        for prefix in BotCommands:
            if reply_text.lower().startswith(f'{prefix}gen'):
                gen_command_found = True
                break
        if not gen_command_found:
            return False
        text = message.text or message.caption
        if not text:
            return False
        return extract_bin_from_text(text) is not None

@dp.message(Command(commands=["gen"], prefix=BotCommands))
@new_task
@SmartDefender
async def generate_handler(message: Message, bot: Bot):
    LOGGER.info(f"Received command: '{message.text}' from user {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
    progress_message = None
    file_name = None
    try:
        user_id = message.from_user.id if message.from_user else None
        user_full_name = "Anonymous"
        if message.from_user:
            user_full_name = message.from_user.first_name or "Anonymous"
            if message.from_user.last_name:
                user_full_name += f" {message.from_user.last_name}"
        progress_message = await send_message(
            chat_id=message.chat.id,
            text="<b>Generating Credit Cards...</b>",
            parse_mode=ParseMode.HTML
        )
        user_input = None
        if message.reply_to_message and message.reply_to_message.text:
            user_input = message.reply_to_message.text
            extracted_bin = extract_bin_from_text(user_input)
            if extracted_bin:
                user_input = extracted_bin
                LOGGER.info(f"Using extracted BIN from reply text: {extracted_bin}")
        elif message.reply_to_message and message.reply_to_message.caption:
            user_input = message.reply_to_message.caption
            extracted_bin = extract_bin_from_text(user_input)
            if extracted_bin:
                user_input = extracted_bin
                LOGGER.info(f"Using extracted BIN from reply caption: {extracted_bin}")
        else:
            user_input = get_args(message)
            if not user_input:
                await progress_message.edit_text(
                    text="<b>Please Provide A Valid Bin ❌</b>",
                    parse_mode=ParseMode.HTML
                )
                return
        bin, month, year, cvv, amount = parse_input(user_input)
        if not bin:
            LOGGER.error(f"Invalid BIN extracted from: {user_input}")
            await progress_message.edit_text(
                text="<b>Sorry Bin Must Be 6-15 Digits ❌</b>",
                parse_mode=ParseMode.HTML
            )
            return
        if amount > CC_GEN_LIMIT:
            await progress_message.edit_text(
                text=f"<b>You Can Only Generate Upto {CC_GEN_LIMIT} Credit Cards ❌</b>",
                parse_mode=ParseMode.HTML
            )
            return
        if cvv is not None:
            is_amex = is_amex_bin(bin)
            if is_amex and len(cvv) != 4:
                await progress_message.edit_text(
                    text="<b>Invalid CVV format. CVV must be 4 digits for AMEX ❌</b>",
                    parse_mode=ParseMode.HTML
                )
                return
        clean_bin_for_api = bin[:6]
        bin_info = await get_bin_info(clean_bin_for_api, bot, message)
        if not bin_info:
            await delete_messages(message.chat.id, progress_message.message_id)
            return
        bank = bin_info["data"][0].get("issuer")
        card_type = bin_info["data"][0].get("type", "Unknown")
        card_scheme = bin_info["data"][0].get("brand", "Unknown")
        bank_text = bank.upper() if bank else "Unknown"
        country_code = bin_info["data"][0].get("country_code", "Unknown")
        country_name, flag_emoji = get_flag(country_code)
        bin_info_text = f"{card_scheme.upper()} - {card_type.upper()}"
        cards = generate_credit_card(bin, amount, month, year, cvv)
        if not cards:
            await progress_message.edit_text(
                text="<b>Sorry Bin Must Be 6-15 Digits ❌</b>",
                parse_mode=ParseMode.HTML
            )
            return
        await delete_messages(message.chat.id, progress_message.message_id)
        if amount <= 10:
            card_text = "\n".join([f"<code>{card}</code>" for card in cards])
            response_text = f"<b>BIN ⇾</b> {bin}\n<b>Amount ⇾</b> {amount}\n\n{card_text}\n\n<b>Bank:</b> {bank_text}\n<b>Country:</b> {country_name} {flag_emoji}\n<b>BIN Info:</b> {bin_info_text}"
            buttons = SmartButtons()
            callback_data = f"regenerate|{bin.replace(' ', '_')}|{month if month else 'xx'}|{year if year else 'xx'}|{cvv if cvv else ('xxxx' if is_amex_bin(bin) else 'xxx')}|{amount}|{user_id if user_id else '0'}"
            buttons.button(text="Re-Generate", callback_data=callback_data)
            reply_markup = buttons.build_menu(b_cols=1)
            await send_message(
                chat_id=message.chat.id,
                text=response_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
            LOGGER.info(f"Successfully sent credit card generation response to chat {message.chat.id}")
        else:
            os.makedirs('./downloads', exist_ok=True)
            file_name = f"./downloads/{bin}_x_{amount}.txt"
            try:
                with open(file_name, "w") as file:
                    file.write("\n".join(cards))
                caption = f"<b>🔍 Multiple CC Generate Successful 📋</b>\n<b>━━━━━━━━━━━━━━━━</b>\n<b>BIN:</b> {bin}\n<b>BIN Info:</b> {bin_info_text}\n<b>Bank:</b> {bank_text}\n<b>Country:</b> {country_name} {flag_emoji}\n<b>━━━━━━━━━━━━━━━━</b>\n<b>👁 Thanks For Using Our Tool ✅</b>"
                await bot.send_document(
                    chat_id=message.chat.id,
                    document=FSInputFile(path=file_name),
                    caption=caption,
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Successfully sent credit card document to chat {message.chat.id}")
            except Exception as e:
                LOGGER.error(f"Error sending document to chat {message.chat.id}: {str(e)}")
                await Smart_Notify(bot, "/gen", e, message)
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>Sorry Bro API Response Unavailable</b>",
                    parse_mode=ParseMode.HTML
                )
            finally:
                if file_name:
                    clean_download(file_name)
    except Exception as e:
        LOGGER.error(f"Error in generate_handler for chat {message.chat.id}: {str(e)}")
        await Smart_Notify(bot, "/gen", e, message)
        if progress_message:
            try:
                await progress_message.edit_text(
                    text="<b>Sorry, an error occurred while generating cards ❌</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Edited progress message with error in chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                await Smart_Notify(bot, "/gen", edit_e, message)
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>Sorry, an error occurred while generating cards ❌</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Sent error message to chat {message.chat.id}")
        else:
            await send_message(
                chat_id=message.chat.id,
                text="<b>Sorry, an error occurred while generating cards ❌</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Sent error message to chat {message.chat.id}")
        if file_name:
            clean_download(file_name)

@dp.message(BinPatternFilter())
@new_task
@SmartDefender
async def auto_generate_handler(message: Message, bot: Bot):
    LOGGER.info(f"Received auto-generate command from user {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
    progress_message = None
    file_name = None
    try:
        user_id = message.from_user.id if message.from_user else None
        user_full_name = "Anonymous"
        if message.from_user:
            user_full_name = message.from_user.first_name or "Anonymous"
            if message.from_user.last_name:
                user_full_name += f" {message.from_user.last_name}"
        current_text = message.text or message.caption
        if not current_text:
            return
        extracted_bin = extract_bin_from_text(current_text)
        if not extracted_bin:
            return
        user_input = extracted_bin
        LOGGER.info(f"Auto-extracted BIN from reply: {extracted_bin}")
        bin, month, year, cvv, amount = parse_input(user_input)
        if not bin:
            await send_message(
                chat_id=message.chat.id,
                text="<b>Sorry Bin Must Be 6-15 Digits ❌</b>",
                parse_mode=ParseMode.HTML
            )
            return
        if amount > CC_GEN_LIMIT:
            await send_message(
                chat_id=message.chat.id,
                text=f"<b>You Can Only Generate Upto {CC_GEN_LIMIT} Credit Cards ❌</b>",
                parse_mode=ParseMode.HTML
            )
            return
        if cvv is not None:
            is_amex = is_amex_bin(bin)
            if is_amex and len(cvv) != 4:
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>Invalid CVV format. CVV must be 4 digits for AMEX ❌</b>",
                    parse_mode=ParseMode.HTML
                )
                return
        clean_bin_for_api = bin[:6]
        progress_message = await send_message(
            chat_id=message.chat.id,
            text="<b>Generating Credit Cards...</b>",
            parse_mode=ParseMode.HTML
        )
        LOGGER.info("Auto-generating Credit Cards...")
        bin_info = await get_bin_info(clean_bin_for_api, bot, message)
        if not bin_info:
            await delete_messages(message.chat.id, progress_message.message_id)
            return
        bank = bin_info["data"][0].get("issuer")
        card_type = bin_info["data"][0].get("type", "Unknown")
        card_scheme = bin_info["data"][0].get("brand", "Unknown")
        bank_text = bank.upper() if bank else "Unknown"
        country_code = bin_info["data"][0].get("country_code", "Unknown")
        country_name, flag_emoji = get_flag(country_code)
        bin_info_text = f"{card_scheme.upper()} - {card_type.upper()}"
        cards = generate_credit_card(bin, amount, month, year, cvv)
        if not cards:
            await progress_message.edit_text(
                text="<b>Sorry Bin Must Be 6-15 Digits ❌</b>",
                parse_mode=ParseMode.HTML
            )
            return
        await delete_messages(message.chat.id, progress_message.message_id)
        if amount <= 10:
            card_text = "\n".join([f"<code>{card}</code>" for card in cards])
            response_text = f"<b>BIN ⇾</b> {bin}\n<b>Amount ⇾</b> {amount}\n\n{card_text}\n\n<b>Bank:</b> {bank_text}\n<b>Country:</b> {country_name} {flag_emoji}\n<b>BIN Info:</b> {bin_info_text}"
            buttons = SmartButtons()
            callback_data = f"regenerate|{bin.replace(' ', '_')}|{month if month else 'xx'}|{year if year else 'xx'}|{cvv if cvv else ('xxxx' if is_amex_bin(bin) else 'xxx')}|{amount}|{user_id if user_id else '0'}"
            buttons.button(text="Re-Generate", callback_data=callback_data)
            reply_markup = buttons.build_menu(b_cols=1)
            await send_message(
                chat_id=message.chat.id,
                text=response_text,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
            LOGGER.info(f"Successfully sent auto-generated credit card response to chat {message.chat.id}")
        else:
            os.makedirs('./downloads', exist_ok=True)
            file_name = f"./downloads/{bin}_x_{amount}.txt"
            try:
                with open(file_name, "w") as file:
                    file.write("\n".join(cards))
                caption = f"<b>🔍 Multiple CC Generate Successful 📋</b>\n<b>━━━━━━━━━━━━━━━━</b>\n<b>BIN:</b> {bin}\n<b>BIN Info:</b> {bin_info_text}\n<b>Bank:</b> {bank_text}\n<b>Country:</b> {country_name} {flag_emoji}\n<b>━━━━━━━━━━━━━━━━</b>\n<b>👁 Thanks For Using Our Tool ✅</b>"
                await bot.send_document(
                    chat_id=message.chat.id,
                    document=FSInputFile(path=file_name),
                    caption=caption,
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Successfully sent auto-generated credit card document to chat {message.chat.id}")
            except Exception as e:
                LOGGER.error(f"Error sending document to chat {message.chat.id}: {str(e)}")
                await Smart_Notify(bot, "/gen", e, message)
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>Sorry Bro API Response Unavailable</b>",
                    parse_mode=ParseMode.HTML
                )
            finally:
                if file_name:
                    clean_download(file_name)
    except Exception as e:
        LOGGER.error(f"Error in auto_generate_handler for chat {message.chat.id}: {str(e)}")
        await Smart_Notify(bot, "/gen", e, message)
        if progress_message:
            try:
                await progress_message.edit_text(
                    text="<b>Sorry, an error occurred while generating cards ❌</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Edited progress message with error in chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                await Smart_Notify(bot, "/gen", edit_e, message)
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>Sorry, an error occurred while generating cards ❌</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Sent error message to chat {message.chat.id}")
        else:
            await send_message(
                chat_id=message.chat.id,
                text="<b>Sorry, an error occurred while generating cards ❌</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Sent error message to chat {message.chat.id}")
        if file_name:
            clean_download(file_name)

@dp.callback_query(lambda c: c.data.startswith("regenerate|"))
@new_task
@SmartDefender
async def regenerate_callback(callback_query: CallbackQuery, bot: Bot):
    LOGGER.info(f"Received callback query: '{callback_query.data}' from user {callback_query.from_user.id if callback_query.from_user else 'Unknown'} in chat {callback_query.message.chat.id}")
    file_name = None
    try:
        user_id = callback_query.from_user.id if callback_query.from_user else None
        user_full_name = "Anonymous"
        if callback_query.from_user:
            user_full_name = callback_query.from_user.first_name or "Anonymous"
            if callback_query.from_user.last_name:
                user_full_name += f" {callback_query.from_user.last_name}"
        data_parts = callback_query.data.split('|')
        if len(data_parts) != 7:
            await callback_query.answer("Invalid callback data", show_alert=True)
            return
        bin = data_parts[1].replace('_', ' ')
        month = data_parts[2] if data_parts[2] != 'xx' else None
        year = data_parts[3] if data_parts[3] != 'xx' else None
        cvv = data_parts[4] if data_parts[4] not in ['xxx', 'xxxx'] else None
        try:
            amount = int(data_parts[5])
        except ValueError:
            await callback_query.answer("Invalid amount in callback data", show_alert=True)
            return
        if not bin:
            await callback_query.answer("Sorry Bin Must Be 6-15 Digits ❌", show_alert=True)
            return
        if amount > CC_GEN_LIMIT:
            await callback_query.answer(f"You can only generate up to {CC_GEN_LIMIT} credit cards ❌", show_alert=True)
            return
        if cvv is not None:
            is_amex = is_amex_bin(bin)
            if is_amex and len(cvv) != 4:
                await callback_query.answer("Invalid CVV format. CVV must be 4 digits for AMEX ❌", show_alert=True)
                return
        clean_bin_for_api = bin[:6]
        bin_info = await get_bin_info(clean_bin_for_api, bot, callback_query.message)
        if not bin_info:
            return
        bank = bin_info["data"][0].get("issuer")
        card_type = bin_info["data"][0].get("type", "Unknown")
        card_scheme = bin_info["data"][0].get("brand", "Unknown")
        bank_text = bank.upper() if bank else "Unknown"
        country_code = bin_info["data"][0].get("country_code", "Unknown")
        country_name, flag_emoji = get_flag(country_code)
        bin_info_text = f"{card_scheme.upper()} - {card_type.upper()}"
        cards = generate_credit_card(bin, amount, month, year, cvv)
        if not cards:
            await callback_query.answer("Sorry Bin Must Be 6-15 Digits ❌", show_alert=True)
            return
        if amount <= 10:
            card_text = "\n".join([f"<code>{card}</code>" for card in cards])
            response_text = f"<b>BIN ⇾</b> {bin}\n<b>Amount ⇾</b> {amount}\n\n{card_text}\n\n<b>Bank:</b> {bank_text}\n<b>Country:</b> {country_name} {flag_emoji}\n<b>BIN Info:</b> {bin_info_text}"
            buttons = SmartButtons()
            callback_data = f"regenerate|{bin.replace(' ', '_')}|{month if month else 'xx'}|{year if year else 'xx'}|{cvv if cvv else ('xxxx' if is_amex_bin(bin) else 'xxx')}|{amount}|{user_id if user_id else '0'}"
            buttons.button(text="Re-Generate", callback_data=callback_data)
            reply_markup = buttons.build_menu(b_cols=1)
            try:
                await callback_query.message.edit_text(
                    text=response_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup
                )
                LOGGER.info(f"Successfully sent regenerated credit card response to chat {callback_query.message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit message in chat {callback_query.message.chat.id}: {str(edit_e)}")
                await Smart_Notify(bot, "regenerate_callback", edit_e, callback_query.message)
                await send_message(
                    chat_id=callback_query.message.chat.id,
                    text=response_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=reply_markup
                )
                LOGGER.info(f"Successfully sent regenerated credit card response to chat {callback_query.message.chat.id}")
        else:
            os.makedirs('./downloads', exist_ok=True)
            file_name = f"./downloads/{bin}_x_{amount}.txt"
            try:
                with open(file_name, "w") as file:
                    file.write("\n".join(cards))
                caption = f"<b>🔍 Multiple CC Generate Successful 📋</b>\n<b>━━━━━━━━━━━━━━━━</b>\n<b>BIN:</b> {bin}\n<b>BIN Info:</b> {bin_info_text}\n<b>Bank:</b> {bank_text}\n<b>Country:</b> {country_name} {flag_emoji}\n<b>━━━━━━━━━━━━━━━━</b>\n<b>👁 Thanks For Using Our Tool ✅</b>"
                await bot.send_document(
                    chat_id=callback_query.message.chat.id,
                    document=FSInputFile(path=file_name),
                    caption=caption,
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Successfully sent regenerated credit card document to chat {callback_query.message.chat.id}")
            except Exception as e:
                LOGGER.error(f"Error sending document to chat {callback_query.message.chat.id}: {str(e)}")
                await Smart_Notify(bot, "regenerate_callback", e, callback_query.message)
                await send_message(
                    chat_id=callback_query.message.chat.id,
                    text="<b>Sorry Bro API Response Unavailable</b>",
                    parse_mode=ParseMode.HTML
                )
            finally:
                if file_name:
                    clean_download(file_name)
    except Exception as e:
        LOGGER.error(f"Error in regenerate_callback for chat {callback_query.message.chat.id}: {str(e)}")
        await Smart_Notify(bot, "regenerate_callback", e, callback_query.message)
        await send_message(
            chat_id=callback_query.message.chat.id,
            text="<b>Sorry, an error occurred while regenerating cards ❌</b>",
            parse_mode=ParseMode.HTML
        )
        LOGGER.info(f"Sent error message to chat {callback_query.message.chat.id}")
        if file_name:
            clean_download(file_name)
