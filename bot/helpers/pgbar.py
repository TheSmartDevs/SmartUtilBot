import time
from .logger import LOGGER

async def progress_bar(current, total, status_message, start_time, last_update_time):
    elapsed_time = time.time() - start_time
    percentage = (current / total) * 100
    progress = f"{'▓' * int(percentage // 5)}{'░' * (20 - int(percentage // 5))}"
    speed = current / elapsed_time / 1024 / 1024
    uploaded = current / 1024 / 1024
    total_size = total / 1024 / 1024

    if time.time() - last_update_time[0] < 1:
        return
    last_update_time[0] = time.time()

    text = (
        f"<b>Smart Upload Progress Bar ✅</b>\n"
        f"<b>━━━━━━━━━━━━━━━━━</b>\n"
        f"{progress}\n"
        f"<b>Percentage:</b> {percentage:.2f}%\n"
        f"<b>Speed:</b> {speed:.2f} MB/s\n"
        f"<b>Status:</b> {uploaded:.2f} MB of {total_size:.2f} MB\n"
        f"<b>━━━━━━━━━━━━━━━━━</b>\n"
        f"<b>Smooth Transfer → Activated ✅</b>"
    )
    try:
        await status_message.edit_text(text, parse_mode="HTML")
    except Exception as e:
        LOGGER.error(f"Error updating progress: {e}")