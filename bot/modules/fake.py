import asyncio
import pycountry
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from bot import dp
from bot.helpers.utils import new_task
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.buttons import SmartButtons
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from config import COMMAND_PREFIX
from smartfaker import Faker

def get_flag(country_code):
    try:
        country = pycountry.countries.get(alpha_2=country_code)
        if not country:
            raise ValueError("Invalid country code")
        country_name = country.name
        flag_emoji = chr(0x1F1E6 + ord(country_code[0]) - ord('A')) + chr(0x1F1E6 + ord(country_code[1]) - ord('A'))
        return country_name, flag_emoji
    except:
        return "Unknown", ""

def resolve_country(input_str):
    input_str = input_str.strip().upper()
    country_mappings = {
        "UK": ("GB", "United Kingdom"),
        "UAE": ("AE", "United Arab Emirates"),
        "AE": ("AE", "United Arab Emirates"),
        "UNITED KINGDOM": ("GB", "United Kingdom"),
        "UNITED ARAB EMIRATES": ("AE", "United Arab Emirates")
    }
    if input_str in country_mappings:
        return country_mappings[input_str]
    if len(input_str) == 2:
        country = pycountry.countries.get(alpha_2=input_str)
        if country:
            return country.alpha_2, country.name
    try:
        country = pycountry.countries.search_fuzzy(input_str)[0]
        return country.alpha_2, country.name
    except LookupError:
        return input_str, input_str

async def get_fake_address(country_code):
    try:
        fake = Faker()
        result = await fake.address(country_code, 1)
        if isinstance(result, dict) and "country" in result:
            return result
        LOGGER.error(f"SmartFaker returned invalid response: {result}")
        return None
    except Exception as e:
        LOGGER.error(f"Error fetching fake address: {str(e)}")
        return None

@dp.message(Command(commands=["fake", "rnd"], prefix=BotCommands))
@new_task
async def fake_handler(message: Message, bot: Bot):
    LOGGER.info(f"Received command: '{message.text}' from user {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
    progress_message = None
    try:
        args = get_args(message)
        if not args:
            progress_message = await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Please Provide A Country Code or Name</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"No country provided in chat {message.chat.id}")
            return
        country_input = args[0]
        country_code, country_name = resolve_country(country_input)
        if not country_code:
            progress_message = await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Invalid Country Code or Name</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Invalid country {country_input} in chat {message.chat.id}")
            return
        progress_message = await send_message(
            chat_id=message.chat.id,
            text="<b>Generating Fake Address...</b>",
            parse_mode=ParseMode.HTML
        )
        address = await get_fake_address(country_code)
        if not address:
            await delete_messages(message.chat.id, [progress_message.message_id])
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Sorry, Fake Address Generation Failed</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Failed to generate fake address for {country_code} in chat {message.chat.id}")
            return
        country_name, flag_emoji = get_flag(country_code)
        address_text = (
            f"<b>Address for {country_name} {flag_emoji}</b>\n"
            f"<b>━━━━━━━━━━━━━</b>\n"
            f"<b>- Street :</b> <code>{address['building_number']} {address['street_name']}</code>\n"
            f"<b>- Street Name :</b> <code>{address['street_name']}</code>\n"
            f"<b>- Currency :</b> <code>{address['currency']}</code>\n"
            f"<b>- Full Name :</b> <code>{address['person_name']}</code>\n"
            f"<b>- City/Town/Village :</b> <code>{address['city']}</code>\n"
            f"<b>- Gender :</b> <code>{address['gender']}</code>\n"
            f"<b>- Postal Code :</b> <code>{address['postal_code']}</code>\n"
            f"<b>- Phone Number :</b> <code>{address['phone_number']}</code>\n"
            f"<b>- State :</b> <code>{address['state']}</code>\n"
            f"<b>- Country :</b> <code>{address['country']}</code>\n"
            f"<b>━━━━━━━━━━━━━</b>\n"
            f"<b>Click Below Button 👇</b>"
        )
        buttons = SmartButtons()
        buttons.button(text="Copy Postal Code", copy_text=address['postal_code'])
        await delete_messages(message.chat.id, [progress_message.message_id])
        await send_message(
            chat_id=message.chat.id,
            text=address_text,
            parse_mode=ParseMode.HTML,
            reply_markup=buttons.build_menu(b_cols=1)
        )
        LOGGER.info(f"Successfully sent fake address for {country_code} to chat {message.chat.id}")
    except (Exception, TelegramBadRequest) as e:
        LOGGER.error(f"Error processing fake address command in chat {message.chat.id}: {str(e)}")
        await Smart_Notify(bot, "fake", e, message)
        if progress_message:
            try:
                await delete_messages(message.chat.id, [progress_message.message_id])
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Sorry, Fake Address Generation Failed</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Sent fake address error message to chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to delete progress message in chat {message.chat.id}: {str(edit_e)}")
                await Smart_Notify(bot, "fake", edit_e, message)
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Sorry, Fake Address Generation Failed</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Sent fake address error message to chat {message.chat.id}")
        else:
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Sorry, Fake Address Generation Failed</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Sent fake address error message to chat {message.chat.id}")
