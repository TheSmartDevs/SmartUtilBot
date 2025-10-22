from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from bot import dp, SmartAIO
from bot.helpers.utils import new_task
from bot.helpers.botutils import send_message
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.defend import SmartDefender
from bot.helpers.buttons import SmartButtons
from bot.helpers.graph import SmartGraph
from bot.helpers.bindb import smartdb
from datetime import datetime
import asyncio
import pycountry

smart_graph = SmartGraph()

async def init_telegraph(bot: Bot):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            loop.create_task(smart_graph.initialize())
        else:
            await smart_graph.initialize()
        LOGGER.info("Telegraph account initialized successfully")
    except Exception as e:
        LOGGER.error(f"Failed to create or access Telegraph account: {str(e)}")
        await Smart_Notify(bot, "bindb", e, None)

async def process_bins_to_json(api_result, bot: Bot):
    processed = []
    if not api_result or not isinstance(api_result, dict):
        await Smart_Notify(bot, "bindb", "Invalid or empty API result", None)
        return processed
    data = api_result.get("data", [])
    for bin_data in data:
        processed.append({
            "bin": bin_data.get("bin", "Unknown"),
            "bank": bin_data.get("issuer", "Unknown"),
            "country_code": bin_data.get("country_code", "Unknown")
        })
    return processed

async def create_telegraph_page(content: str, part_number: int, bot: Bot) -> list:
    try:
        current_date = datetime.now().strftime("%m-%d")
        truncated_content = content[:40000]
        max_size_bytes = 20 * 1024
        pages = []
        page_content = ""
        current_size = 0
        lines = truncated_content.splitlines(keepends=True)
        part_count = part_number
        for line in lines:
            line_bytes = line.encode('utf-8', errors='ignore')
            if current_size + len(line_bytes) > max_size_bytes and page_content:
                page_url = await smart_graph.create_page(
                    title=f"Smart-Tool-Bin-DB---Part-{part_count}-{current_date}",
                    content=page_content,
                    author_name="ISmartCoder",
                    author_url="https://t.me/TheSmartDev"
                )
                if not page_url:
                    return []
                pages.append(page_url)
                page_content = ""
                current_size = 0
                part_count += 1
                await asyncio.sleep(0.5)
            page_content += line
            current_size += len(line_bytes)
        if page_content:
            page_url = await smart_graph.create_page(
                title=f"Smart-Tool-Bin-DB---Part-{part_count}-{current_date}",
                content=page_content,
                author_name="TheSmartDev",
                author_url="https://t.me/TheSmartDevs"
            )
            if not page_url:
                return []
            pages.append(page_url)
            await asyncio.sleep(0.5)
        return pages
    except Exception as e:
        LOGGER.error(f"Failed to create Telegraph page: {str(e)}")
        await Smart_Notify(bot, "bindb", e, None)
        return []

def generate_message(bins, identifier):
    message = f"<b>Smart Util ⚙️ - Bin database 📋</b>\n<b>━━━━━━━━━━━━━━━━━━</b>\n\n"
    for bin_data in bins[:10]:
        message += (f"<b>BIN:</b> <code>{bin_data['bin']}</code>\n"
                    f"<b>Bank:</b> {bin_data['bank']}\n"
                    f"<b>Country:</b> {bin_data['country_code']}\n\n")
    return message

def generate_telegraph_content(bins):
    content = ""
    for bin_data in bins:
        content += (f"BIN: {bin_data['bin']}\n"
                    f"Bank: {bin_data['bank']}\n"
                    f"Country: {bin_data['country_code']}\n\n")
    return content

@dp.message(Command(commands=["bin"], prefix=BotCommands))
@new_task
@SmartDefender
async def bin_handler(message: Message, bot: Bot):
    LOGGER.info(f"Received command: '{message.text}' from user {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
    await init_telegraph(bot)
    progress_message = None
    try:
        progress_message = await send_message(
            chat_id=message.chat.id,
            text="<b>Checking input...</b>",
            parse_mode=ParseMode.HTML
        )
        user_input = message.text.split(maxsplit=1)
        if len(user_input) == 1:
            await progress_message.edit_text(
                text="<b>Please provide a BIN number. e.g. /bin 222714</b>",
                parse_mode=ParseMode.HTML
            )
            return
        bin_number = user_input[1].strip()
        try:
            await progress_message.edit_text(
                text=f"<b>Finding BIN {bin_number}...</b>",
                parse_mode=ParseMode.HTML
            )
        except TelegramBadRequest as edit_e:
            LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
            await Smart_Notify(bot, "bin", edit_e, message)
            progress_message = await send_message(
                chat_id=message.chat.id,
                text=f"<b>Finding BIN {bin_number}...</b>",
                parse_mode=ParseMode.HTML
            )
        bin_result = await smartdb.get_bin_info(bin_number)
        processed_bins = await process_bins_to_json(bin_result, bot)
        if not processed_bins:
            await progress_message.edit_text(
                text="<b>Sorry, BIN Not Found ❌</b>",
                parse_mode=ParseMode.HTML
            )
            return
        message_text = generate_message(processed_bins, bin_number)
        keyboard = None
        if len(processed_bins) > 10:
            bins_content = generate_telegraph_content(processed_bins[10:])
            content_size = len(bins_content.encode('utf-8'))
            telegraph_urls = await create_telegraph_page(bins_content, part_number=1, bot=bot)
            if telegraph_urls:
                buttons = SmartButtons()
                if content_size <= 20 * 1024:
                    buttons.button("Full Output", url=telegraph_urls[0])
                else:
                    for i, url in enumerate(telegraph_urls, start=1):
                        buttons.button(f"Output {i}", url=url)
                keyboard = buttons.build_menu(b_cols=2)
            else:
                message_text += "\n<b>Sorry, failed to upload additional results to Telegraph ❌</b>"
        await progress_message.edit_text(
            text=message_text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
        LOGGER.info(f"Successfully sent BIN database response for BIN {bin_number} to chat {message.chat.id}")
    except Exception as e:
        LOGGER.error(f"Exception in bin_handler for chat {message.chat.id}: {str(e)}")
        await Smart_Notify(bot, "bin", e, message)
        if progress_message:
            try:
                await progress_message.edit_text(
                    text="<b>Sorry, an error occurred while fetching BIN data ❌</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Edited progress message with error in chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                await Smart_Notify(bot, "bin", edit_e, message)
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>Sorry, an error occurred while fetching BIN data ❌</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Sent error message to chat {message.chat.id}")
        else:
            await send_message(
                chat_id=message.chat.id,
                text="<b>Sorry, an error occurred while fetching BIN data ❌</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Sent error message to chat {message.chat.id}")

@dp.message(Command(commands=["bindb"], prefix=BotCommands))
@new_task
@SmartDefender
async def bindb_handler(message: Message, bot: Bot):
    LOGGER.info(f"Received command: '{message.text}' from user {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
    await init_telegraph(bot)
    progress_message = None
    try:
        progress_message = await send_message(
            chat_id=message.chat.id,
            text="<b>Checking input...</b>",
            parse_mode=ParseMode.HTML
        )
        user_input = message.text.split(maxsplit=1)
        if len(user_input) == 1:
            await progress_message.edit_text(
                text="<b>Please provide a country name or code. e.g. /bindb BD or /bindb Bangladesh</b>",
                parse_mode=ParseMode.HTML
            )
            return
        country_input = user_input[1].upper()
        if country_input in ["UK", "UNITED KINGDOM"]:
            country_code = "GB"
            country_name = "United Kingdom"
        else:
            country = pycountry.countries.search_fuzzy(country_input)[0] if len(country_input) > 2 else pycountry.countries.get(alpha_2=country_input)
            if not country:
                await progress_message.edit_text(
                    text="<b>Invalid country name or code</b>",
                    parse_mode=ParseMode.HTML
                )
                return
            country_code = country.alpha_2.upper()
            country_name = country.name
        try:
            await progress_message.edit_text(
                text=f"<b>Finding Bins With Country {country_name}...</b>",
                parse_mode=ParseMode.HTML
            )
        except TelegramBadRequest as edit_e:
            LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
            await Smart_Notify(bot, "bindb", edit_e, message)
            progress_message = await send_message(
                chat_id=message.chat.id,
                text=f"<b>Finding Bins With Country {country_name}...</b>",
                parse_mode=ParseMode.HTML
            )
        bins_result = await smartdb.get_bins_by_country(country_code, limit=8000)
        processed_bins = await process_bins_to_json(bins_result, bot)
        if not processed_bins:
            await progress_message.edit_text(
                text="<b>Sorry No Bins Found ❌</b>",
                parse_mode=ParseMode.HTML
            )
            return
        message_text = generate_message(processed_bins, country_code)
        keyboard = None
        if len(processed_bins) > 10:
            bins_content = generate_telegraph_content(processed_bins[10:])
            content_size = len(bins_content.encode('utf-8'))
            telegraph_urls = await create_telegraph_page(bins_content, part_number=1, bot=bot)
            if telegraph_urls:
                buttons = SmartButtons()
                if content_size <= 20 * 1024:
                    buttons.button("Full Output", url=telegraph_urls[0])
                else:
                    for i, url in enumerate(telegraph_urls, start=1):
                        buttons.button(f"Output {i}", url=url)
                keyboard = buttons.build_menu(b_cols=2)
            else:
                message_text += "\n<b>Sorry, failed to upload additional results to Telegraph ❌</b>"
        await progress_message.edit_text(
            text=message_text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
        LOGGER.info(f"Successfully sent BIN database response for country {country_name} to chat {message.chat.id}")
    except Exception as e:
        LOGGER.error(f"Exception in bindb_handler for chat {message.chat.id}: {str(e)}")
        await Smart_Notify(bot, "bindb", e, message)
        if progress_message:
            try:
                await progress_message.edit_text(
                    text="<b>Sorry, an error occurred while fetching BIN data ❌</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Edited progress message with error in chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                await Smart_Notify(bot, "bindb", edit_e, message)
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>Sorry, an error occurred while fetching BIN data ❌</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Sent error message to chat {message.chat.id}")
        else:
            await send_message(
                chat_id=message.chat.id,
                text="<b>Sorry, an error occurred while fetching BIN data ❌</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Sent error message to chat {message.chat.id}")

@dp.message(Command(commands=["binbank"], prefix=BotCommands))
@new_task
@SmartDefender
async def binbank_handler(message: Message, bot: Bot):
    LOGGER.info(f"Received command: '{message.text}' from user {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
    await init_telegraph(bot)
    progress_message = None
    try:
        progress_message = await send_message(
            chat_id=message.chat.id,
            text="<b>Checking input...</b>",
            parse_mode=ParseMode.HTML
        )
        user_input = message.text.split(maxsplit=1)
        if len(user_input) == 1:
            await progress_message.edit_text(
                text="<b>Please provide a bank name. e.g. /binbank Pubali</b>",
                parse_mode=ParseMode.HTML
            )
            return
        bank_name = user_input[1].title()
        try:
            await progress_message.edit_text(
                text=f"<b>Finding Bins With Bank {bank_name}...</b>",
                parse_mode=ParseMode.HTML
            )
        except TelegramBadRequest as edit_e:
            LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
            await Smart_Notify(bot, "binbank", edit_e, message)
            progress_message = await send_message(
                chat_id=message.chat.id,
                text=f"<b>Finding Bins With Bank {bank_name}...</b>",
                parse_mode=ParseMode.HTML
            )
        bins_result = await smartdb.get_bins_by_bank(bank_name, limit=8000)
        processed_bins = await process_bins_to_json(bins_result, bot)
        if not processed_bins:
            await progress_message.edit_text(
                text="<b>Sorry No Bins Found ❌</b>",
                parse_mode=ParseMode.HTML
            )
            return
        message_text = generate_message(processed_bins, bank_name)
        keyboard = None
        if len(processed_bins) > 10:
            bins_content = generate_telegraph_content(processed_bins[10:])
            content_size = len(bins_content.encode('utf-8'))
            telegraph_urls = await create_telegraph_page(bins_content, part_number=1, bot=bot)
            if telegraph_urls:
                buttons = SmartButtons()
                if content_size <= 20 * 1024:
                    buttons.button("Full Output", url=telegraph_urls[0])
                else:
                    for i, url in enumerate(telegraph_urls, start=1):
                        buttons.button(f"Output {i}", url=url)
                keyboard = buttons.build_menu(b_cols=2)
            else:
                message_text += "\n<b>Sorry, failed to upload additional results to Telegraph ❌</b>"
        await progress_message.edit_text(
            text=message_text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard
        )
        LOGGER.info(f"Successfully sent BIN database response for bank {bank_name} to chat {message.chat.id}")
    except Exception as e:
        LOGGER.error(f"Exception in binbank_handler for chat {message.chat.id}: {str(e)}")
        await Smart_Notify(bot, "binbank", e, message)
        if progress_message:
            try:
                await progress_message.edit_text(
                    text="<b>Sorry, an error occurred while fetching BIN data ❌</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Edited progress message with error in chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                await Smart_Notify(bot, "binbank", edit_e, message)
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>Sorry, an error occurred while fetching BIN data ❌</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Sent error message to chat {message.chat.id}")
        else:
            await send_message(
                chat_id=message.chat.id,
                text="<b>Sorry, an error occurred while fetching BIN data ❌</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Sent error message to chat {message.chat.id}")