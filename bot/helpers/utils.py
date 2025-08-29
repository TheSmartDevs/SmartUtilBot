import asyncio
import os
import shutil
from bot.helpers import LOGGER

def new_task(func):
    async def wrapper(*args, **kwargs):
        return await func(*args, **kwargs)
    return asyncio.create_task(wrapper)

async def clean_download(path):
    try:
        if os.path.isfile(path):
            os.remove(path)
            LOGGER.info(f"Deleted file: {path}")
        elif os.path.isdir(path):
            shutil.rmtree(path)
            LOGGER.info(f"Deleted directory: {path}")
        else:
            LOGGER.warning(f"Path does not exist: {path}")
        return True
    except Exception as e:
        LOGGER.error(f"Failed to clean download path {path}: {e}")
        return False