# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
#  Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
import asyncio
import functools
import os
from bot.helpers.logger import LOGGER

def new_task(func):
    async def wrapper(message, bot, **kwargs):
        try:
            task = asyncio.create_task(func(message, bot))
            task.add_done_callback(lambda t: t.exception() and LOGGER.error(f"{func.__name__} failed: {t.exception()}"))
        except Exception as e:
            LOGGER.error(f"new_task error in {func.__name__}: {e}")
    return wrapper

def clean_download(*files):
    for file in files:
        try:
            if os.path.exists(file):
                os.remove(file)
                LOGGER.info(f"Removed temporary file {file}")
        except Exception as e:
            LOGGER.error(f"clean_download error for {file}: {e}")