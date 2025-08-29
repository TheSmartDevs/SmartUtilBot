from pyrogram import Client
from .helpers import LOGGER
from ..config import API_ID, API_HASH, BOT_TOKEN, SESSION_STRING

LOGGER.info("Creating Bot Client From BOT_TOKEN")
SmartGram = Client(
    "SmartUtilBot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=1000
)
LOGGER.info("Bot Client Created Successfully!")

LOGGER.info("Creating User Client From SESSION_STRING")
SmartUser = Client(
    "SmartUserBot",
    session_string=SESSION_STRING,
    workers=1000
)
LOGGER.info("User Client Successfully Created!")