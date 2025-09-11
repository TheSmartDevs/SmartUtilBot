from aiogram import Bot
from aiogram.filters import Command, BaseFilter
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from bot import dp
from bot.helpers.utils import new_task
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.buttons import SmartButtons
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.defend import SmartDefender
from smartbindb import SmartBinDB
import pycountry
import random
import asyncio

async def get_bin_info(bin: str, bot: Bot, message: Message):
    try:
        smartdb = SmartBinDB()
        result = await smartdb.get_bin_info(bin)
        if result.get("status") == "SUCCESS" and result.get("data") and isinstance(result["data"], list) and len(result["data"]) > 0:
            return result
        else:
            LOGGER.error(f"SmartBinDB returned invalid response: {result}")
            await Smart_Notify(bot, "extp", f"SmartBinDB invalid response: {result}", message)
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
        await Smart_Notify(bot, "extp", e, message)
        await send_message(
            chat_id=message.chat.id,
            text=error_message,
            parse_mode=ParseMode.HTML
        )
        return None

def luhn_algorithm(number):
    def digits_of(n):
        return [int(d) for d in str(n)]
    digits = digits_of(number)
    checksum = 0
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum += sum(odd_digits)
    for d in even_digits:
        checksum += sum(digits_of(d * 2))
    return checksum % 10 == 0

def generate_extrapolated_numbers(bin, amount=5):
    extrapolated_numbers = set()
    while len(extrapolated_numbers) < amount:
        number = bin + ''.join(random.choices('0123456789', k=9))
        check_sum = 0
        reverse_digits = number[::-1]
        for i, digit in enumerate(reverse_digits):
            n = int(digit)
            if i % 2 == 0:
                n = n * 2
                if n > 9:
                    n = n - 9
            check_sum += n
        last_digit = (10 - (check_sum % 10)) % 10
        final_number = number + str(last_digit)
        if luhn_algorithm(final_number):
            extrapolated_numbers.add(final_number)
    return list(extrapolated_numbers)

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

class ExtrapolateCallbackFilter(BaseFilter):
    async def __call__(self, callback_query: CallbackQuery):
        return callback_query.data.startswith("regenerate_")

@dp.message(Command(commands=["extp"], prefix=BotCommands))
@new_task
@SmartDefender
async def extrapolate_handler(message: Message, bot: Bot):
    LOGGER.info(f"Received /extp command from user: {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
    progress_message = None
    try:
        args = get_args(message)
        if len(args) != 1 or not args[0].isdigit() or len(args[0]) != 6:
            progress_message = await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Please provide a valid 6-digit BIN</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.warning(f"Invalid BIN provided by user: {message.from_user.id}")
            return

        bin = args[0]
        progress_message = await send_message(
            chat_id=message.chat.id,
            text="<b>Extrapolation In Progress...✨</b>",
            parse_mode=ParseMode.HTML
        )

        bin_info = await get_bin_info(bin, bot, message)
        if not bin_info:
            await progress_message.edit_text(
                text="<b>BIN Not Found In Database ❌</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"BIN {bin} not found in database for user: {message.from_user.id}")
            return

        extrapolated_numbers = generate_extrapolated_numbers(bin)
        formatted_numbers = [f"<code>{num[:random.randint(8, 12)] + 'x' * (len(num) - random.randint(8, 12))}</code>" for num in extrapolated_numbers]
        country_code = bin_info["data"][0].get("country_code", "Unknown")
        country_name, flag_emoji = get_flag(country_code)
        bank = bin_info["data"][0].get("issuer", "None")
        card_type = bin_info["data"][0].get("type", "None")
        card_scheme = bin_info["data"][0].get("brand", "None")

        result_message = (
            "<b>🔍 Extrapolation Details From Smart Database 📋</b>\n"
            "<b>━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>Extrapolated BIN:</b> <code>{bin}</code>\n"
            f"<b>Amount:</b> {len(formatted_numbers)}\n\n" +
            "\n".join(formatted_numbers) + "\n\n" +
            f"<b>Bank:</b> {bank.upper()}\n"
            f"<b>Country:</b> {country_name.upper()} {flag_emoji}\n"
            f"<b>Bin Info:</b> {card_scheme.upper()} - {card_type.upper()}\n"
            "<b>━━━━━━━━━━━━━━━━━━</b>\n"
            "<b>🔍 Smart Extrapolation → Activated ✅</b>"
        )

        buttons = SmartButtons()
        buttons.button(text="Re-Generate", callback_data=f"regenerate_{bin}")
        await delete_messages(message.chat.id, progress_message.message_id)
        await send_message(
            chat_id=message.chat.id,
            text=result_message,
            parse_mode=ParseMode.HTML,
            reply_markup=buttons.build_menu(b_cols=1)
        )
        LOGGER.info(f"Successfully sent extrapolated numbers for BIN {bin} to chat {message.chat.id}")

    except Exception as e:
        LOGGER.error(f"Error processing /extp command in chat {message.chat.id}: {str(e)}")
        await Smart_Notify(bot, "extp", e, message)
        if progress_message:
            try:
                await progress_message.edit_text(
                    text="<b>❌ Sorry Bro Extrapolation API Error</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Edited progress message with extrapolation error in chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                await Smart_Notify(bot, "extp", edit_e, message)
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Sorry Bro Extrapolation API Error</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Sent extrapolation error message to chat {message.chat.id}")
        else:
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Sorry Bro Extrapolation API Error</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Sent extrapolation error message to chat {message.chat.id}")

@dp.callback_query(ExtrapolateCallbackFilter())
@new_task
@SmartDefender
async def regenerate_callback(callback_query: CallbackQuery, bot: Bot):
    LOGGER.info(f"Received regenerate callback from user: {callback_query.from_user.id} in chat {callback_query.message.chat.id}")
    try:
        bin = callback_query.data.split("_")[1]

        bin_info = await get_bin_info(bin, bot, callback_query.message)
        if not bin_info:
            await callback_query.message.edit_text(
                text="<b>❌ Invalid BIN provided</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"BIN {bin} not found in database for user: {callback_query.from_user.id}")
            return

        extrapolated_numbers = generate_extrapolated_numbers(bin)
        formatted_numbers = [f"<code>{num[:random.randint(8, 12)] + 'x' * (len(num) - random.randint(8, 12))}</code>" for num in extrapolated_numbers]
        country_code = bin_info["data"][0].get("country_code", "Unknown")
        country_name, flag_emoji = get_flag(country_code)
        bank = bin_info["data"][0].get("issuer", "None")
        card_type = bin_info["data"][0].get("type", "None")
        card_scheme = bin_info["data"][0].get("brand", "None")

        regenerated_message = (
            "<b>🔍 Extrapolation Details From Smart Database 📋</b>\n"
            "<b>━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>Extrapolated BIN:</b> <code>{bin}</code>\n"
            f"<b>Amount:</b> {len(formatted_numbers)}\n\n" +
            "\n".join(formatted_numbers) + "\n\n" +
            f"<b>Bank:</b> {bank.upper()}\n"
            f"<b>Country:</b> {country_name.upper()} {flag_emoji}\n"
            f"<b>Bin Info:</b> {card_scheme.upper()} - {card_type.upper()}\n"
            "<b>━━━━━━━━━━━━━━━━━━</b>\n"
            "<b>🔍 Smart Extrapolation → Activated ✅</b>"
        )

        buttons = SmartButtons()
        buttons.button(text="Re-Generate", callback_data=f"regenerate_{bin}")
        await callback_query.message.edit_text(
            text=regenerated_message,
            parse_mode=ParseMode.HTML,
            reply_markup=buttons.build_menu(b_cols=1)
        )
        LOGGER.info(f"Successfully regenerated extrapolated numbers for BIN {bin} for user {callback_query.from_user.id}")

    except Exception as e:
        LOGGER.error(f"Error processing regenerate callback in chat {callback_query.message.chat.id}: {str(e)}")
        await Smart_Notify(bot, "extp", e, callback_query.message)
        await callback_query.message.edit_text(
            text="<b>❌ Sorry Bro Extrapolation API Error</b>",
            parse_mode=ParseMode.HTML
        )
        LOGGER.info(f"Sent extrapolation error message to chat {callback_query.message.chat.id}")
