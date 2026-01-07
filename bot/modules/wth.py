from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, URLInputFile
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from bot import dp
from bot.helpers.utils import new_task
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.defend import SmartDefender
from bot.helpers.buttons import SmartButtons
from config import A360APIBASEURL
import aiohttp
import re

async def get_weather_data(area: str):
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{A360APIBASEURL}/wth?area={area}"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("status") == "success":
                        return data
                    else:
                        LOGGER.error(f"Weather API returned error: {data}")
                        return None
                else:
                    LOGGER.error(f"Weather API request failed with status {response.status}")
                    return None
    except Exception as e:
        LOGGER.error(f"Error fetching weather data: {str(e)}")
        return None

@dp.message(Command(commands=["wth", "weather"], prefix=BotCommands))
@new_task
@SmartDefender
async def weather_handler(message: Message, bot: Bot):
    LOGGER.info(f"Received command: '{message.text}' from user {message.from_user.id if message.from_user else 'Unknown'} in chat {message.chat.id}")
    progress_message = None
    try:
        args = get_args(message)
        if not args:
            progress_message = await send_message(
                chat_id=message.chat.id,
                text="<b>Please provide a city name. Example: /wth Faridpur ❌</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"No city provided in chat {message.chat.id}")
            return
        
        progress_message = await send_message(
            chat_id=message.chat.id,
            text="<b>Processing Weather Results...</b>",
            parse_mode=ParseMode.HTML
        )
        
        area = args[0]
        weather_data = await get_weather_data(area)
        
        if not weather_data:
            await progress_message.edit_text(
                text=f"<b>🔍 Weather data unavailable for {area.capitalize()}. Please check the city name or try again later. ❌</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Weather data unavailable for {area} in chat {message.chat.id}")
            return
        
        location = weather_data["location"]
        current = weather_data["current"]
        
        buttons = SmartButtons()
        buttons.button("🕒 12h Forecast", callback_data=f"wth_12h_{area}")
        buttons.button("📅 7-Day Forecast", callback_data=f"wth_7d_{area}")
        buttons.button("🌬 Air Quality", callback_data=f"wth_aqi_{area}")
        buttons.button("⚠️ Weather Alerts", callback_data=f"wth_alert_{area}")
        buttons.button("🔄 Refresh Current", callback_data=f"wth_refresh_{area}")
        buttons.button("🗺 Maps & Radar", callback_data=f"wth_map_{area}")
        reply_markup = buttons.build_menu(b_cols=2)
        
        caption = (
            f"<b>🔍 Showing Weather for {location['city']}</b>\n"
            f"<b>━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>🌍 Location:</b> {location['city']}, {location['country']}\n"
            f"<b>🕒 Time:</b> {current['time']}\n"
            f"<b>📅 Date:</b> {current['date']}\n"
            f"<b>🌡 Temperature:</b> {current['temperature']}°C (Feels like: {current['feels_like']}°C)\n"
            f"<b>💧 Humidity:</b> {current['humidity']}%\n"
            f"<b>🌬 Wind:</b> {current['wind_speed']} m/s from {current['wind_direction']}°\n"
            f"<b>🌅 Sunrise:</b> {current['sunrise']}\n"
            f"<b>🌆 Sunset:</b> {current['sunset']}\n"
            f"<b>🌤 Weather:</b> {current['weather']}\n"
            f"<b>━━━━━━━━━━━━━━━━━</b>\n"
            f"👁 Please Use Below Buttons For Navigate ✅"
        )
        
        await progress_message.delete()
        
        image_url = weather_data.get("image_url")
        if image_url:
            photo_message = await bot.send_photo(
                chat_id=message.chat.id,
                photo=URLInputFile(image_url),
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
        else:
            await send_message(
                chat_id=message.chat.id,
                text=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
        
        LOGGER.info(f"Successfully sent weather details for {area} to chat {message.chat.id}")
        
    except Exception as e:
        LOGGER.error(f"Error processing weather command in chat {message.chat.id}: {str(e)}")
        await Smart_Notify(bot, "weather", e, message)
        if progress_message:
            try:
                await progress_message.edit_text(
                    text="<b>❌ Sorry Bro Weather API Error</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Edited progress message with weather error in chat {message.chat.id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit progress message in chat {message.chat.id}: {str(edit_e)}")
                await Smart_Notify(bot, "weather", edit_e, message)
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Sorry Bro Weather API Error</b>",
                    parse_mode=ParseMode.HTML
                )
                LOGGER.info(f"Sent weather error message to chat {message.chat.id}")
        else:
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Sorry Bro Weather API Error</b>",
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Sent weather error message to chat {message.chat.id}")

@dp.callback_query(lambda c: c.data and re.match(r"^wth_(12h|7d|aqi|alert|map|refresh|menu)_.+$", c.data))
@new_task
async def weather_callback_handler(callback_query: CallbackQuery, bot: Bot):
    match = re.match(r"^wth_(12h|7d|aqi|alert|map|refresh|menu)_(.+)$", callback_query.data)
    if not match:
        LOGGER.error(f"Invalid callback_data format: {callback_query.data}")
        await callback_query.answer("Error: Invalid button data. Please try again.", show_alert=True)
        return
    
    action, city = match.groups()
    
    try:
        await callback_query.answer("Loading.....")
        
        weather_data = await get_weather_data(city)
        
        if not weather_data:
            await callback_query.message.edit_caption(
                caption=f"<b>🔍 Weather data unavailable for {city.capitalize()}. Please try again later. ❌</b>",
                parse_mode=ParseMode.HTML
            )
            return
        
        location = weather_data["location"]
        current = weather_data["current"]
        
        buttons = SmartButtons()
        
        if action in ["12h", "7d", "aqi", "alert", "map"]:
            buttons.button("🔙 Back", callback_data=f"wth_menu_{city}")
            reply_markup = buttons.build_menu(b_cols=1)
        else:
            buttons.button("🕒 12h Forecast", callback_data=f"wth_12h_{city}")
            buttons.button("📅 7-Day Forecast", callback_data=f"wth_7d_{city}")
            buttons.button("🌬 Air Quality", callback_data=f"wth_aqi_{city}")
            buttons.button("⚠️ Weather Alerts", callback_data=f"wth_alert_{city}")
            buttons.button("🔄 Refresh Current", callback_data=f"wth_refresh_{city}")
            buttons.button("🗺 Maps & Radar", callback_data=f"wth_map_{city}")
            reply_markup = buttons.build_menu(b_cols=2)
        
        if action == "12h":
            hourly_data = weather_data["hourly_forecast"]
            hourly_text = "\n".join([f"{h['time']}: {h['temperature']}°C {h['weather']}" for h in hourly_data])
            message = (
                f"<b>🕒 12-Hour Forecast for {location['city']}</b>\n"
                f"<b>━━━━━━━━━━━━━━━━━</b>\n"
                f"{hourly_text}\n"
                f"<b>━━━━━━━━━━━━━━━━</b>\n"
                f"Click Below Buttons To Navigate"
            )
            await callback_query.message.edit_caption(caption=message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        
        elif action == "7d":
            daily_data = weather_data["daily_forecast"]
            daily_text = "\n".join([f"{d['day']}: {d['min_temp']} / {d['max_temp']}°C {d['weather']}" for d in daily_data])
            message = (
                f"<b>📅 7-Day Forecast for {location['city']}</b>\n"
                f"<b>━━━━━━━━━━━━━━━━━</b>\n"
                f"{daily_text}\n"
                f"<b>━━━━━━━━━━━━━━━━</b>\n"
                f"Click Below Buttons To Navigate"
            )
            await callback_query.message.edit_caption(caption=message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        
        elif action == "aqi":
            aqi = weather_data["air_quality"]
            message = (
                f"<b>🌬 Air Quality for {location['city']}</b>\n"
                f"<b>━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>Overall AQI:</b> {aqi['level']} 🟡\n"
                f"<b>CO:</b> {aqi['carbon_monoxide']} µg/m³\n"
                f"<b>NO2:</b> {aqi['nitrogen_dioxide']} µg/m³\n"
                f"<b>O3:</b> {aqi['ozone']} µg/m³\n"
                f"<b>PM2.5:</b> {aqi['pm2_5']} µg/m³\n"
                f"<b>PM10:</b> {aqi['pm10']} µg/m³\n"
                f"<b>━━━━━━━━━━━━━━━━</b>\n"
                f"Click Below Buttons To Navigate"
            )
            await callback_query.message.edit_caption(caption=message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        
        elif action == "alert":
            message = (
                f"<b>🛡 Weather Alerts for {location['city']}</b>\n"
                f"<b>━━━━━━━━━━━━━━━━━</b>\n"
                f"✅ No active weather alerts\n"
                f"<b>━━━━━━━━━━━━━━━━</b>\n"
                f"Click Below Buttons To Navigate"
            )
            await callback_query.message.edit_caption(caption=message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        
        elif action == "map":
            maps = weather_data["maps"]
            map_links = [
                f'<a href="{maps["temperature"]}">🌡 Temperature Map</a>',
                f'<a href="{maps["clouds"]}">☁️ Cloud Cover</a>',
                f'<a href="{maps["precipitation"]}">🌧 Precipitation</a>',
                f'<a href="{maps["wind"]}">💨 Wind Speed</a>',
                f'<a href="{maps["pressure"]}">🌊 Pressure</a>'
            ]
            maps_text = "\n".join(map_links)
            message = (
                f"<b>🗺 Weather Maps for {location['city']}</b>\n"
                f"<b>━━━━━━━━━━━━━━━━━</b>\n"
                f"{maps_text}\n"
                f"<b>━━━━━━━━━━━━━━━━</b>\n"
                f"Click Below Buttons To Navigate"
            )
            await callback_query.message.edit_caption(caption=message, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        
        elif action == "refresh":
            new_weather_data = await get_weather_data(city)
            if not new_weather_data:
                await callback_query.answer("Failed to refresh weather data.", show_alert=True)
                return
            
            new_location = new_weather_data["location"]
            new_current = new_weather_data["current"]
            
            old_caption = callback_query.message.caption if callback_query.message.caption else ""
            
            caption = (
                f"<b>🔍 Showing Weather for {new_location['city']}</b>\n"
                f"<b>━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>🌍 Location:</b> {new_location['city']}, {new_location['country']}\n"
                f"<b>🕒 Time:</b> {new_current['time']}\n"
                f"<b>📅 Date:</b> {new_current['date']}\n"
                f"<b>🌡 Temperature:</b> {new_current['temperature']}°C (Feels like: {new_current['feels_like']}°C)\n"
                f"<b>💧 Humidity:</b> {new_current['humidity']}%\n"
                f"<b>🌬 Wind:</b> {new_current['wind_speed']} m/s from {new_current['wind_direction']}°\n"
                f"<b>🌅 Sunrise:</b> {new_current['sunrise']}\n"
                f"<b>🌆 Sunset:</b> {new_current['sunset']}\n"
                f"<b>🌤 Weather:</b> {new_current['weather']}\n"
                f"<b>━━━━━━━━━━━━━━━━━</b>\n"
                f"👁 Please Use Below Buttons For Navigate ✅"
            )
            
            new_image_url = new_weather_data.get("image_url")
            old_image_url = weather_data.get("image_url")
            
            if old_caption == caption and new_image_url == old_image_url:
                await callback_query.answer("Weather data has not changed.", show_alert=True)
                return
            
            try:
                if new_image_url and new_image_url != old_image_url:
                    await callback_query.message.edit_media(
                        media={"type": "photo", "media": URLInputFile(new_image_url), "caption": caption, "parse_mode": ParseMode.HTML},
                        reply_markup=reply_markup
                    )
                    await callback_query.answer("Weather data refreshed!", show_alert=False)
                elif old_caption != caption:
                    await callback_query.message.edit_caption(caption=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
                    await callback_query.answer("Weather data refreshed!", show_alert=False)
                else:
                    await callback_query.answer("Weather data has not changed.", show_alert=True)
            except TelegramBadRequest as e:
                if "message is not modified" in str(e):
                    await callback_query.answer("Weather data has not changed.", show_alert=True)
                else:
                    raise
        
        elif action == "menu":
            caption = (
                f"<b>🔍 Showing Weather for {location['city']}</b>\n"
                f"<b>━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>🌍 Location:</b> {location['city']}, {location['country']}\n"
                f"<b>🕒 Time:</b> {current['time']}\n"
                f"<b>📅 Date:</b> {current['date']}\n"
                f"<b>🌡 Temperature:</b> {current['temperature']}°C (Feels like: {current['feels_like']}°C)\n"
                f"<b>💧 Humidity:</b> {current['humidity']}%\n"
                f"<b>🌬 Wind:</b> {current['wind_speed']} m/s from {current['wind_direction']}°\n"
                f"<b>🌅 Sunrise:</b> {current['sunrise']}\n"
                f"<b>🌆 Sunset:</b> {current['sunset']}\n"
                f"<b>🌤 Weather:</b> {current['weather']}\n"
                f"<b>━━━━━━━━━━━━━━━━━</b>\n"
                f"👁 Please Use Below Buttons For Navigate ✅"
            )
            await callback_query.message.edit_caption(caption=caption, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
        
        LOGGER.info(f"Successfully processed callback {action} for city {city}")
        
    except Exception as e:
        LOGGER.error(f"Callback query error: {str(e)}")
        await callback_query.message.edit_caption(caption="<b>❌ Sorry API Not Reachable</b>", parse_mode=ParseMode.HTML)
        await Smart_Notify(bot, f"weather callback {action}", e, callback_query.message)