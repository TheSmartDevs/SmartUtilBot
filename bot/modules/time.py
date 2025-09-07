# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
#  Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
import pytz
import pycountry
from datetime import datetime
import calendar
from PIL import Image, ImageDraw, ImageFont
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile, InputMediaPhoto
from aiogram.enums import ParseMode
from bot import dp
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.buttons import SmartButtons
from bot.helpers.defend import SmartDefender
import asyncio

def get_flag(country_code):
    try:
        country = pycountry.countries.get(alpha_2=country_code)
        if not country:
            return None, "🏳️"
        country_name = country.name
        flag_emoji = ''.join(chr(0x1F1E6 + ord(c) - ord('A')) for c in country_code.upper())
        if not all(0x1F1E6 <= ord(c) <= 0x1F1FF for c in flag_emoji):
            return country_name, "🏳️"
        return country_name, flag_emoji
    except Exception as e:
        LOGGER.error(f"Error in get_flag: {str(e)}")
        return None, "🏳️"

async def create_clock_image(country_name, time_str, date_str, day_str, output_path):
    width, height = 1240, 740
    bg_color = (8, 12, 18)
    card_color = (19, 26, 34)
    accent_color = (0, 230, 255)
    white = (255, 255, 255)
    gray = (168, 177, 186)
    font_time = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 110)
    font_date = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 48)
    font_day = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 42)
    font_country = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    margin = 60
    card_rect = [margin, margin, width - margin, height - margin]
    draw.rounded_rectangle(card_rect, radius=30, fill=card_color, outline=accent_color, width=4)
    line_margin = 100
    line_width = width - 2 * (margin + line_margin)
    top_line_y = 180
    bottom_line_y = height - margin - line_margin
    draw.line([(margin + line_margin, top_line_y), (margin + line_margin + line_width, top_line_y)], fill=accent_color, width=3)
    draw.line([(margin + line_margin, bottom_line_y), (margin + line_margin + line_width, bottom_line_y)], fill=accent_color, width=3)
    dot_radius = 6
    side_dot_x_left = margin + 10
    side_dot_x_right = width - margin - 10
    dot_y_positions = [260, 310, 360]
    for y in dot_y_positions:
        draw.ellipse((side_dot_x_left - dot_radius, y - dot_radius, side_dot_x_left + dot_radius, y + dot_radius), fill=accent_color)
        draw.ellipse((side_dot_x_right - dot_radius, y - dot_radius, side_dot_x_right + dot_radius, y + dot_radius), fill=accent_color)
    time_bbox = draw.textbbox((0, 0), time_str, font=font_time)
    time_x = (width - (time_bbox[2] - time_bbox[0])) // 2
    time_y = 220
    draw.text((time_x, time_y), time_str, font=font_time, fill=white)
    date_bbox = draw.textbbox((0, 0), date_str, font=font_date)
    date_x = (width - (date_bbox[2] - date_bbox[0])) // 2
    date_y = time_y + 120
    draw.text((date_x, date_y), date_str, font=font_date, fill=gray)
    day_spacing = 30
    day_bbox = draw.textbbox((0, 0), day_str, font=font_day)
    day_x = (width - (day_bbox[2] - day_bbox[0])) // 2
    day_y = date_y + 55 + day_spacing
    draw.text((day_x, day_y), day_str, font=font_day, fill=white)
    country_spacing = 25
    country_bbox = draw.textbbox((0, 0), country_name, font=font_country)
    country_x = (width - (country_bbox[2] - country_bbox[0])) // 2
    country_y = day_y + 55 + country_spacing
    draw.text((country_x, country_y), country_name, font=font_country, fill=accent_color)
    img.save(output_path)
    return output_path

async def create_calendar_image(country_code):
    try:
        country = pycountry.countries.get(alpha_2=country_code)
        country_name = country.name if country else "Unknown"
        time_zones = {
            "gb": ["Europe/London"],
            "ae": ["Asia/Dubai"]
        }.get(country_code, pytz.country_timezones.get(country_code))
        if time_zones:
            tz = pytz.timezone(time_zones[0])
            now = datetime.now(tz)
            time_str = now.strftime("%I:%M:%S %p")
            date_str = now.strftime("%d %b, %Y")
            day_str = now.strftime("%A")
        else:
            time_str = "00:00:00 AM"
            date_str = "Unknown Date"
            day_str = "Unknown Day"
        output_path = f"calendar_{country_code}.png"
        await create_clock_image(country_name, time_str, date_str, day_str, output_path)
        return output_path
    except Exception as e:
        LOGGER.error(f"Error creating calendar image: {str(e)}")
        return None

async def get_calendar_markup(year, month, country_code):
    cal = calendar.Calendar()
    month_days = cal.monthdayscalendar(year, month)
    prev_month = month - 1 if month > 1 else 12
    next_month = month + 1 if month < 12 else 1
    prev_year = year - 1 if month == 1 else year
    next_year = year + 1 if month == 12 else year
    buttons = SmartButtons()
    buttons.button(text="<", callback_data=f"nav_{country_code}_{prev_year}_{prev_month}", position="footer")
    buttons.button(text=">", callback_data=f"nav_{country_code}_{next_year}_{next_month}", position="footer")
    for day in ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]:
        buttons.button(text=day, callback_data=f"alert_{country_code}_{year}_{month}")
    for week in month_days:
        for day in week:
            if day == 0:
                buttons.button(text=" ", callback_data=f"alert_{country_code}_{year}_{month}")
            else:
                buttons.button(text=str(day), callback_data=f"day_{country_code}_{month:02d}_{day:02d}")
    country = pycountry.countries.get(alpha_2=country_code)
    country_name = country.name if country else "Unknown"
    flag_emoji = get_flag(country_code)[1]
    time_zones = {
        "gb": ["Europe/London"],
        "ae": ["Asia/Dubai"]
    }.get(country_code, pytz.country_timezones.get(country_code))
    if time_zones:
        tz = pytz.timezone(time_zones[0])
        now_tz = datetime.now(tz)
        current_time = now_tz.strftime("%I:%M:%S %p")
    else:
        now_tz = datetime.now()
        current_time = "00:00:00 AM"
    if month == now_tz.month and year == now_tz.year:
        buttons.button(text=f"{calendar.month_name[month]} {year} 📅", callback_data=f"alert_{country_code}_{year}_{month}", position="header")
        buttons.button(text=f"{now_tz.strftime('%d %b, %Y')}", callback_data=f"alert_{country_code}_{year}_{month}", position="header")
        buttons.button(text=f"{flag_emoji} {country_name} | {current_time}", callback_data=f"alert_{country_code}_{year}_{month}", position="header")
    else:
        buttons.button(text=f"{calendar.month_name[month]} {year}", callback_data=f"alert_{country_code}_{year}_{month}", position="header")
    return buttons.build_menu(b_cols=7, h_cols=2, f_cols=2)

async def get_time_and_calendar(country_input, year=None, month=None):
    country_code = None
    try:
        country_input = country_input.lower().strip()
        if country_input in ["uk", "united kingdom"]:
            country_code = "gb"
        elif country_input in ["uae", "united arab emirates"]:
            country_code = "ae"
        else:
            try:
                country = pycountry.countries.search_fuzzy(country_input)[0]
                country_code = country.alpha_2
            except LookupError:
                country_code = country_input.upper().strip()
                if len(country_code) != 2 or not pycountry.countries.get(alpha_2=country_code):
                    raise ValueError("Invalid country code or name")
        country_name, flag_emoji = get_flag(country_code)
        if not country_name:
            country_name = "Unknown"
        time_zones = {
            "gb": ["Europe/London"],
            "ae": ["Asia/Dubai"]
        }.get(country_code, pytz.country_timezones.get(country_code))
        if time_zones:
            tz = pytz.timezone(time_zones[0])
            now = datetime.now(tz)
            time_str = now.strftime("%I:%M:%S %p")
        else:
            now = datetime.now()
            time_str = "00:00:00 AM"
        if year is None or month is None:
            year = now.year
            month = now.month
        date_str = now.strftime("%d %b, %Y")
        message = f"📅 {flag_emoji} <b>{country_name} Calendar | ⏰ {time_str} 👇</b>"
        calendar_markup = await get_calendar_markup(year, month, country_code)
        return (message, calendar_markup, country_code, year, month)
    except ValueError as e:
        raise ValueError(str(e))

@dp.message(Command(commands=["time", "calendar"], prefix=BotCommands))
@new_task
@SmartDefender
async def handle_time_command(message: Message, bot: Bot):
    chat_id = message.chat.id
    args = get_args(message)
    if not args:
        await send_message(
            chat_id=chat_id,
            text="<b>❌ Ensure you provide a valid country code or name.</b>",
            parse_mode=ParseMode.HTML
        )
        return
    country_input = args[0].lower().strip()
    temp_files = []
    try:
        header_text, calendar_markup, country_code, year, month = await get_time_and_calendar(country_input)
        output_path = await create_calendar_image(country_code)
        if not output_path:
            raise Exception("Failed to create calendar image")
        temp_files.append(output_path)
        await bot.send_photo(
            chat_id=chat_id,
            photo=FSInputFile(output_path),
            caption=header_text,
            parse_mode=ParseMode.HTML,
            reply_markup=calendar_markup
        )
        clean_download(*temp_files)
    except ValueError as e:
        LOGGER.error(f"ValueError in handle_time_command: {str(e)}")
        await send_message(
            chat_id=chat_id,
            text="<b>❌ Ensure you provide a valid country code or name.</b>",
            parse_mode=ParseMode.HTML
        )
        clean_download(*temp_files)
    except Exception as e:
        LOGGER.error(f"Exception in handle_time_command: {str(e)}")
        await Smart_Notify(bot, "/time", e, message)
        await send_message(
            chat_id=chat_id,
            text="<b>The Country Is Not In My Database</b>",
            parse_mode=ParseMode.HTML
        )
        clean_download(*temp_files)

@dp.callback_query(lambda c: c.data.startswith('nav_'))
@SmartDefender
async def handle_calendar_nav(callback_query):
    try:
        _, country_code, year, month = callback_query.data.split('_')
        year = int(year)
        month = int(month)
        temp_files = []
        try:
            header_text, calendar_markup, country_code, _, _ = await get_time_and_calendar(country_code, year, month)
            output_path = await create_calendar_image(country_code)
            if not output_path:
                raise Exception("Failed to create calendar image")
            temp_files.append(output_path)
            await callback_query.message.edit_media(
                media=InputMediaPhoto(
                    media=FSInputFile(output_path),
                    caption=header_text,
                    parse_mode=ParseMode.HTML
                ),
                reply_markup=calendar_markup
            )
            clean_download(*temp_files)
            await callback_query.answer()
        except Exception as e:
            LOGGER.error(f"Exception in handle_calendar_nav: {str(e)}")
            await Smart_Notify(bot, "calendar_nav", e, callback_query.message)
            await send_message(
                chat_id=callback_query.message.chat.id,
                text="<b>Sorry, failed to update calendar</b>",
                parse_mode=ParseMode.HTML
            )
            clean_download(*temp_files)
    except Exception as e:
        LOGGER.error(f"Exception in handle_calendar_nav: {str(e)}")
        await callback_query.answer("Sorry Invalid Button Query", show_alert=True)

@dp.callback_query(lambda c: c.data.startswith('alert_'))
@SmartDefender
async def handle_alert(callback_query):
    await callback_query.answer("This Is The Button For Calendar", show_alert=True)

@dp.callback_query(lambda c: c.data.startswith('day_'))
@SmartDefender
async def handle_day_click(callback_query):
    try:
        _, country_code, month, day = callback_query.data.split('_')
        month = int(month)
        day = int(day)
        await callback_query.answer(f"{day} {calendar.month_name[month]} - No holiday", show_alert=True)
    except Exception as e:
        LOGGER.error(f"Exception in handle_day_click: {str(e)}")
        await callback_query.answer("Sorry Invalid Button Query", show_alert=True)