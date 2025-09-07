# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
#  Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
import asyncio
import logging
from config import BOT_TOKEN, API_ID, API_HASH, SESSION_STRING
from bot.helpers.logger import LOGGER
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from pyrogram import Client

logging.basicConfig(level=logging.INFO)

LOGGER.info("Creating Bot Client From BOT_TOKEN")
SmartAIO = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
SmartPyro = Client(
    name="SmartUtilBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)
LOGGER.info("Creating User Client From SESSION_STRING")
SmartUserBot = Client(
    "SmartUser",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    workers=10
)
LOGGER.info("User Client Created Successfully !")
LOGGER.info("Bot Client Created Successfully!")

__all__ = ["SmartAIO", "dp", "SmartPyro", "SmartUserBot"]
