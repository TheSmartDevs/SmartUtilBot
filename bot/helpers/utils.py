import asyncio
import functools
import shutil
from bot.helpers.logger import LOGGER

def new_task(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            task = asyncio.create_task(func(*args, **kwargs))
            task.add_done_callback(lambda t: t.exception() and LOGGER.error(f"{func.__name__} failed: {t.exception()}"))
        except Exception as e:
            LOGGER.error(f"new_task error in {func.__name__}: {e}")
    return wrapper

def clean_download():
    try:
        LOGGER.info("Cleaning Up Files From Downloads Folder")
        shutil.rmtree('./downloads')
    except FileNotFoundError:
        pass
    except Exception as e:
        LOGGER.error(f"clean_download error: {e}")