from PIL import Image, ImageDraw, ImageFont, ImageEnhance
import os
import aiohttp
import asyncio
from aiogram import Bot
from aiogram.filters import Command, BaseFilter
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.enums import ParseMode
from bot import dp
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages
from bot.helpers.commands import BotCommands
from bot.helpers.buttons import SmartButtons
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from config import A360APIBASEURL

BASE_URL = f"{A360APIBASEURL}/binance/price"

async def fetch_crypto_data(token=None):
    try:
        url = f"{BASE_URL}?token={token}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response.raise_for_status()
                data = await response.json()
                if not data.get("success", False):
                    LOGGER.error(f"API returned success: false for {token}")
                    raise Exception("API returned success: false")
                LOGGER.info(f"Successfully fetched data for {token}")
                return data['data']
    except Exception as e:
        LOGGER.error(f"Error fetching data for {token}: {e}")
        raise Exception("<b>❌ Data unavailable or invalid token symbol </b>")

async def create_crypto_info_card(
    symbol: str,
    change: str,
    last_price: str,
    high: str,
    low: str,
    volume: str,
    quote_volume: str,
    output_path: str = "crypto_card.png"
):
    if not output_path.lower().endswith(".png"):
        output_path += ".png"
    outer_width, outer_height = 1200, 800
    inner_width, inner_height = 1160, 760
    background_color = (20, 20, 30)
    inner_color = (30, 30, 40)
    border_color = (0, 255, 150)
    text_white = (240, 240, 250)
    text_neon = (0, 255, 150)
    gradient_start = (0, 50, 100)
    gradient_end = (0, 20, 40)
    gap = 35
    try:
        font_title = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 70)
        font_text = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 50)
        font_credit = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 40)
    except IOError:
        raise RuntimeError("Fonts not found. Please install DejaVu Sans or update font paths.")
    img = Image.new("RGB", (outer_width, outer_height), color=background_color)
    draw = ImageDraw.Draw(img)
    for y in range(outer_height):
        r = int(gradient_start[0] + (gradient_end[0] - gradient_start[0]) * y / outer_height)
        g = int(gradient_start[1] + (gradient_end[1] - gradient_start[1]) * y / outer_height)
        b = int(gradient_start[2] + (gradient_end[2] - gradient_start[2]) * y / outer_height)
        draw.line([(0, y), (outer_width, y)], fill=(r, g, b))
    draw.rectangle([(20, 20), (20 + inner_width - 1, 20 + inner_height - 1)], fill=inner_color)
    draw.rectangle([(20, 20), (20 + inner_width - 1, 20 + inner_height - 1)], outline=border_color, width=6)
    draw.rectangle([(22, 22), (22 + inner_width - 5, 22 + inner_height - 5)], outline=(0, 200, 120), width=2)
    title_text = f"Price Info for {symbol.split('USDT')[0]}"
    bbox_title = draw.textbbox((0, 0), title_text, font=font_title)
    x_title = (inner_width - (bbox_title[2] - bbox_title[0])) // 2 + 20
    y = 40
    draw.text((x_title, y), title_text, font=font_title, fill=text_neon)
    y += (bbox_title[3] - bbox_title[1]) + gap
    info_lines = [
        f"Symbol: {symbol}",
        f"Change: {change}",
        f"Last Price: ${last_price}",
        f"24h High: ${high}",
        f"24h Low: ${low}",
        f"24h Volume: {volume}",
        f"24h Quote Volume: ${quote_volume}"
    ]
    for line in info_lines:
        bbox = draw.textbbox((0, 0), line, font=font_text)
        x = (inner_width - (bbox[2] - bbox[0])) // 2 + 20
        draw.text((x, y), line, font=font_text, fill=text_white)
        y += (bbox[3] - bbox[1]) + gap
    credit_text = "Powered By @ISmartCoder"
    bbox_credit = draw.textbbox((0, 0), credit_text, font=font_credit)
    x_credit = (inner_width - (bbox_credit[2] - bbox_credit[0])) // 2 + 20
    draw.text((x_credit + 2, outer_height - 80), credit_text, font=font_credit, fill=(0, 200, 120))
    draw.text((x_credit, outer_height - 82), credit_text, font=font_credit, fill=text_neon)
    img.save(output_path, format="PNG")
    return output_path

def format_crypto_info(data):
    result = (
        f"📊 <b>Symbol:</b> {data['symbol']}\n"
        f"↕️ <b>Change:</b> {data['priceChangePercent']}%\n"
        f"💰 <b>Last Price:</b> {data['lastPrice']}\n"
        f"📈 <b>24h High:</b> {data['highPrice']}\n"
        f"📉 <b>24h Low:</b> {data['lowPrice']}\n"
        f"🔄 <b>24h Volume:</b> {data['volume']}\n"
        f"💵 <b>24h Quote Volume:</b> {data['quoteVolume']}\n\n"
    )
    return result

def extract_price_data_from_caption(caption):
    if not caption:
        return None
    lines = caption.split('\n')
    price_data = {}
    for line in lines:
        if 'Last Price:' in line:
            parts = line.split('Last Price:</b> ')
            price_data['lastPrice'] = parts[1].strip() if len(parts) > 1 else ""
        elif 'Change:' in line:
            parts = line.split('Change:</b> ')
            price_data['priceChangePercent'] = parts[1].strip() if len(parts) > 1 else ""
        elif '24h High:' in line:
            parts = line.split('24h High:</b> ')
            price_data['highPrice'] = parts[1].strip() if len(parts) > 1 else ""
        elif '24h Low:' in line:
            parts = line.split('24h Low:</b> ')
            price_data['lowPrice'] = parts[1].strip() if len(parts) > 1 else ""
        elif '24h Volume:' in line and '24h Quote Volume:' not in line:
            parts = line.split('24h Volume:</b> ')
            price_data['volume'] = parts[1].strip() if len(parts) > 1 else ""
        elif '24h Quote Volume:' in line:
            parts = line.split('24h Quote Volume:</b> ')
            price_data['quoteVolume'] = parts[1].strip() if len(parts) > 1 else ""
    return price_data

def compare_price_data(old_data, new_data):
    if not old_data or not new_data:
        return False
    
    key_fields = ['lastPrice', 'priceChangePercent', 'highPrice', 'lowPrice', 'volume', 'quoteVolume']
    
    for field in key_fields:
        old_value = str(old_data.get(field, '')).strip()
        new_value = str(new_data.get(field, '')).strip()
        if field == 'priceChangePercent':
            new_value = f"{new_value}%"
        if old_value != new_value:
            return False
    return True

class RefreshCallbackFilter(BaseFilter):
    async def __call__(self, callback_query: CallbackQuery):
        return callback_query.data.startswith("refresh_")

@dp.message(Command(commands=["price"], prefix=BotCommands))
@new_task
async def handle_price_command(message: Message, bot: Bot):
    try:
        command = message.text.split()
        if len(command) < 2:
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Please provide a token symbol</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.warning(f"Invalid command format: {message.text} in chat {message.chat.id}")
            return
        token = command[1].upper()
        fetching_message = await send_message(
            chat_id=message.chat.id,
            text="<b>Fetching Token Price..✨</b>",
            parse_mode=ParseMode.HTML
        )
        data = await fetch_crypto_data(token)
        formatted_info = format_crypto_info(data)
        response_message = f"📈 <b>Price Info for {token}:</b>\n\n{formatted_info}"
        image_path = await create_crypto_info_card(
            symbol=data['symbol'],
            change=f"{data['priceChangePercent']}%",
            last_price=data['lastPrice'],
            high=data['highPrice'],
            low=data['lowPrice'],
            volume=data['volume'],
            quote_volume=data['quoteVolume']
        )
        buttons = SmartButtons()
        buttons.button(text="📊 Data Insight", url=f"https://www.binance.com/en/trading_insight/glass?id=44&token={token}")
        buttons.button(text="🔄 Refresh", callback_data=f"refresh_{token}")
        await bot.send_photo(
            chat_id=message.chat.id,
            photo=FSInputFile(path=image_path),
            caption=response_message,
            parse_mode=ParseMode.HTML,
            reply_markup=buttons.build_menu(b_cols=2)
        )
        await delete_messages(message.chat.id, [fetching_message.message_id])
        asyncio.create_task(delete_file_after_delay(image_path))
        LOGGER.info(f"Sent price info with image for {token} to chat {message.chat.id}")
    except Exception as e:
        await delete_messages(message.chat.id, [fetching_message.message_id])
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Nothing Detected From Binance Database</b>",
            parse_mode=ParseMode.HTML
        )
        LOGGER.error(f"Error processing /price for {token}: {e}")
        await Smart_Notify(bot, "/price", e, message)

async def delete_file_after_delay(image_path):
    await asyncio.sleep(600)
    if os.path.exists(image_path):
        os.remove(image_path)
        LOGGER.info(f"Deleted image file {image_path}")
    clean_download()
    LOGGER.info("Downloads folder cleaned after delay")

@dp.callback_query(RefreshCallbackFilter())
@new_task
async def handle_refresh_callback(callback_query: CallbackQuery, bot: Bot):
    try:
        token = callback_query.data.split("_")[1]
        data = await fetch_crypto_data(token)
        old_message = callback_query.message
        old_price_data = extract_price_data_from_caption(old_message.caption)
        
        if compare_price_data(old_price_data, data):
            await callback_query.answer("No price changes since last update", show_alert=True)
            LOGGER.info(f"No price changes detected for {token} in chat {callback_query.message.chat.id}")
            return
        
        image_path = await create_crypto_info_card(
            symbol=data['symbol'],
            change=f"{data['priceChangePercent']}%",
            last_price=data['lastPrice'],
            high=data['highPrice'],
            low=data['lowPrice'],
            volume=data['volume'],
            quote_volume=data['quoteVolume']
        )
        new_formatted_info = format_crypto_info(data)
        response_message = f"📈 <b>Price Info for {token}:</b>\n\n{new_formatted_info}"
        buttons = SmartButtons()
        buttons.button(text="📊 Data Insight", url=f"https://www.binance.com/en/trading_insight/glass?id=44&token={token}")
        buttons.button(text="🔄 Refresh", callback_data=f"refresh_{token}")
        from aiogram.types import InputMediaPhoto
        await callback_query.message.edit_media(
            media=InputMediaPhoto(
                media=FSInputFile(path=image_path),
                caption=response_message,
                parse_mode=ParseMode.HTML
            ),
            reply_markup=buttons.build_menu(b_cols=2)
        )
        await callback_query.answer("Price Updated Successfully!")
        asyncio.create_task(delete_file_after_delay(image_path))
        LOGGER.info(f"Updated price info with image for {token} in chat {callback_query.message.chat.id}")
    except Exception as e:
        await callback_query.answer("No price changes since last update")
        LOGGER.error(f"Error in refresh for {token}: {e}")
        await Smart_Notify(bot, "/price refresh", e, callback_query.message)