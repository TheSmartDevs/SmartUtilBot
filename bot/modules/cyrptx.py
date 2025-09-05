import aiohttp
import asyncio
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from bot import dp
from bot.helpers.utils import new_task
from bot.helpers.botutils import send_message, delete_messages
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from config import A360APIBASEURL

BASE_URL = f"{A360APIBASEURL}/binance/cx"

price_storage = {}

async def get_conversion_data(base_coin: str, target_coin: str, amount: float):
    try:
        url = f"{BASE_URL}?base={base_coin.upper()}&target={target_coin.upper()}&amount={amount}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                if not data.get("success", False):
                    LOGGER.error(f"API returned success: false for {base_coin} to {target_coin}")
                    return None
                LOGGER.info(f"Successfully fetched conversion data for {base_coin} to {target_coin}")
                return data['data']
    except Exception as e:
        LOGGER.error(f"Error fetching conversion data for {base_coin} to {target_coin}: {e}")
        return None

def format_response(data: dict) -> str:
    return (
        "<b>Smart Binance Convert Successful ✅</b>\n"
        "<b>━━━━━━━━━━━━━━━━</b>\n"
        f"<b>Base Coin:</b> {data['base_coin']}\n"
        f"<b>Target Coin:</b> {data['target_coin']}\n"
        f"<b>Amount:</b> {data['amount']:.4f} {data['base_coin']}\n"
        f"<b>Total In USDT:</b> {data['total_in_usdt']:.4f} USDT\n"
        f"<b>Converted Amount:</b> {data['converted_amount']:.4f} {data['target_coin']}\n"
        "<b>━━━━━━━━━━━━━━━━</b>\n"
        "<b>Smooth Coin Converter → Activated ✅</b>"
    )

@dp.message(Command(commands=["cx"], prefix=BotCommands))
@new_task
async def coin_handler(message: Message, bot: Bot):
    command = message.text.split()
    if len(command) < 4:
        await send_message(
            chat_id=message.chat.id,
            text="<b>Invalid format. Use /cx 10 ton usdt</b>",
            parse_mode=ParseMode.HTML
        )
        LOGGER.warning(f"Invalid command format: {message.text} in chat {message.chat.id}")
        return

    try:
        amount = float(command[1])
        if amount <= 0:
            raise ValueError("Amount must be greater than 0")
    except ValueError:
        await send_message(
            chat_id=message.chat.id,
            text="<b>Invalid format. Use <code>/cx 10 ton usdt</code></b>",
            parse_mode=ParseMode.HTML
        )
        LOGGER.warning(f"Invalid amount provided: {command[1]} in chat {message.chat.id}")
        return

    base_coin = command[2].upper()
    target_coin = command[3].upper()

    progress_message = await send_message(
        chat_id=message.chat.id,
        text="<b>Fetching Token Price, Please Wait...</b>",
        parse_mode=ParseMode.HTML
    )

    try:
        data = await get_conversion_data(base_coin, target_coin, amount)
        if data is None:
            await delete_messages(message.chat.id, [progress_message.message_id])
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Failed! This token pair may not exist on Binance.</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.warning(f"Failed to fetch conversion for {base_coin} to {target_coin} in chat {message.chat.id}")
            return

        price_storage[message.chat.id] = data

        await delete_messages(message.chat.id, [progress_message.message_id])
        await send_message(
            chat_id=message.chat.id,
            text=format_response(data),
            parse_mode=ParseMode.HTML
        )
        LOGGER.info(f"Coin conversion result sent for {base_coin} to {target_coin}: {data['converted_amount']} {target_coin} in chat {message.chat.id}")

    except Exception as e:
        await delete_messages(message.chat.id, [progress_message.message_id])
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Failed! This token pair may not exist on Binance.</b>",
            parse_mode=ParseMode.HTML
        )
        LOGGER.error(f"Error processing /cx for {base_coin} to {target_coin} in chat {message.chat.id}: {e}")
        await Smart_Notify(bot, "/cx", e, message)