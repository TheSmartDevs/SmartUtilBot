from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from bot import dp
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.buttons import SmartButtons
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from config import UPDATE_CHANNEL_URL, MULTI_CCGEN_LIMIT
import os
import random
import asyncio

def is_amex_bin(bin_str):
    clean_bin = bin_str.replace('x', '').replace('X', '')
    if len(clean_bin) >= 2:
        first_two = clean_bin[:2]
        return first_two in ['34', '37']
    return False

def luhn_algorithm(card_number):
    def digits_of(n):
        return [int(d) for d in str(n)]
    digits = digits_of(card_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum = sum(odd_digits)
    for d in even_digits:
        checksum += sum(digits_of(d * 2))
    return checksum % 10 == 0

def calculate_luhn_check_digit(card_number):
    def digits_of(n):
        return [int(d) for d in str(n)]
    digits = digits_of(card_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum = sum(odd_digits)
    for d in even_digits:
        checksum += sum(digits_of(d * 2))
    check_digit = (10 - (checksum % 10)) % 10
    return check_digit

def generate_credit_card(bin, amount, month=None, year=None, cvv=None):
    cards = []
    is_amex = is_amex_bin(bin)
    target_length = 14 if is_amex else 15
    cvv_length = 4 if is_amex else 3
    for _ in range(amount):
        while True:
            card_body = ''.join([str(random.randint(0, 9)) if char.lower() == 'x' else char for char in bin])
            remaining_digits = target_length - len(card_body)
            card_body += ''.join([str(random.randint(0, 9)) for _ in range(remaining_digits)])
            check_digit = calculate_luhn_check_digit(card_body)
            card_number = card_body + str(check_digit)
            if luhn_algorithm(card_number):
                card_month = month or f"{random.randint(1, 12):02}"
                card_year = year or random.randint(2024, 2029)
                card_cvv = cvv or ''.join([str(random.randint(0, 9)) for _ in range(cvv_length)])
                cards.append(f"{card_number}|{card_month}|{card_year}|{card_cvv}")
                break
    return cards

def generate_custom_cards(bin, amount, month=None, year=None, cvv=None):
    cards = []
    is_amex = is_amex_bin(bin)
    target_length = 14 if is_amex else 15
    cvv_length = 4 if is_amex else 3
    for _ in range(amount):
        while True:
            card_body = bin.replace('x', '').replace('X', '')
            remaining_digits = target_length - len(card_body)
            card_body += ''.join([str(random.randint(0, 9)) for _ in range(remaining_digits)])
            check_digit = calculate_luhn_check_digit(card_body)
            card_number = card_body + str(check_digit)
            if luhn_algorithm(card_number):
                card_month = month or f"{random.randint(1, 12):02}"
                card_year = year or random.randint(2024, 2029)
                card_cvv = cvv or ''.join([str(random.randint(0, 9)) for _ in range(cvv_length)])
                cards.append(f"{card_number}|{card_month}|{card_year}|{card_cvv}")
                break
    return cards

@dp.message(Command(commands=["mgn", "mgen", "multigen"], prefix=BotCommands))
@new_task
async def multigen_handler(message: Message, bot: Bot):
    LOGGER.info(f"Received /mgen command from user: {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
    progress_message = None
    try:
        args = get_args(message)
        if len(args) < 2:
            progress_message = await send_message(
                chat_id=message.chat.id,
                text="<b>Invalid Arguments ❌</b>\n<b>Use /mgen [BIN1] [BIN2] [BIN3]... [AMOUNT]</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.warning(f"Invalid arguments provided by user: {message.from_user.id}")
            return

        bins = args[:-1]
        try:
            amount = int(args[-1])
        except ValueError:
            progress_message = await send_message(
                chat_id=message.chat.id,
                text="<b>Invalid amount given. Please provide a valid number.</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.warning(f"Invalid amount provided by user: {message.from_user.id}")
            return

        if amount > MULTI_CCGEN_LIMIT:
            progress_message = await send_message(
                chat_id=message.chat.id,
                text=f"<b>You can only generate up to {MULTI_CCGEN_LIMIT} credit cards ❌</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.warning(f"User {message.from_user.id} tried to generate more than {MULTI_CCGEN_LIMIT} cards")
            return

        if any(len(bin) < 6 or len(bin) > 16 for bin in bins):
            progress_message = await send_message(
                chat_id=message.chat.id,
                text="<b>Each BIN should be between 6 and 16 digits ❌</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.warning(f"Invalid BIN length from user: {message.from_user.id}")
            return

        progress_message = await send_message(
            chat_id=message.chat.id,
            text="<b>Generating Credit Cards...✨</b>",
            parse_mode=ParseMode.HTML
        )

        total_cards = []
        for bin in bins:
            if 'x' in bin.lower():
                total_cards.extend(generate_credit_card(bin, amount, None, None, None))
            else:
                total_cards.extend(generate_custom_cards(bin, amount, None, None, None))

        valid_cards = [card for card in total_cards if luhn_algorithm(card.split('|')[0])]
        file_name = f"Generated_CC_{message.chat.id}.txt"

        with open(file_name, "w") as file:
            file.write("\n".join(valid_cards))

        user_full_name = f"{message.from_user.first_name} {message.from_user.last_name or ''}".strip() if message.from_user else message.chat.title or "this group"
        total_bins = len(bins)
        each_bin_cc_amount = amount
        total_amount = total_bins * each_bin_cc_amount
        total_lines = len(valid_cards)
        total_size = total_lines

        caption = (
            f"<b>Smart Multiple CC Generator ✅</b>\n"
            f"<b>━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>⊗ Total Amount:</b> {total_amount}\n"
            f"<b>⊗ Bins:</b> Multiple Bins Used\n"
            f"<b>⊗ Total Size:</b> {total_size}\n"
            f"<b>⊗ Each Bin CC Amount:</b> {each_bin_cc_amount}\n"
            f"<b>⊗ Total Lines:</b> {total_lines}\n"
            f"<b>━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>Smart Multi Gen → Activated ✅</b>"
        )

        buttons = SmartButtons()
        buttons.button(text="Join For Updates", url=UPDATE_CHANNEL_URL)
        await delete_messages(message.chat.id, progress_message.message_id)
        await bot.send_document(
            chat_id=message.chat.id,
            document=FSInputFile(file_name),
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=buttons.build_menu(b_cols=1)
        )
        LOGGER.info(f"Successfully sent generated cards for {len(bins)} BINs to chat {message.chat.id}")

    except Exception as e:
        LOGGER.error(f"Error processing /mgen command in chat {message.chat.id}: {str(e)}")
        await Smart_Notify(bot, "mgen", e, message)
        if progress_message:
            try:
                await progress_message.edit_text(
                    text="<b>❌ Sorry Bro CC Generation Error</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Edited progress message with CC generation error in chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                await Smart_Notify(bot, "mgen", edit_e, message)
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Sorry Bro CC Generation Error</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Sent CC generation error message to chat {message.chat.id}")
        else:
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Sorry Bro CC Generation Error</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Sent CC generation error message to chat {message.chat.id}")
    finally:
        clean_download()