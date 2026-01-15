import os
import asyncio
import aiohttp
import html
from urllib.parse import urlparse
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.enums import ParseMode, ChatType
from bot import dp, SmartAIO
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages
from bot.helpers.logger import LOGGER
from bot.helpers.buttons import SmartButtons
from bot.helpers.commands import BotCommands
from bot.helpers.defend import SmartDefender
from bot.helpers.notify import Smart_Notify
from config import A360APIBASEURL

logger = LOGGER

@dp.message(Command(commands=["ws", "websource"], prefix=BotCommands))
@new_task
@SmartDefender
async def websource(message: Message, bot: Bot):
    if message.chat.type not in [ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP]:
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ This command only works in private or group chats</b>",
            parse_mode=ParseMode.HTML
        )
        return

    if len(message.text.split()) < 2:
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Please provide at least one valid URL.</b>",
            parse_mode=ParseMode.HTML
        )
        return

    url = message.text.split()[1]
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"

    loading_message = await send_message(
        chat_id=message.chat.id,
        text="<b>🔄 Downloading Website Source...</b>\n<i>Extracting HTML, CSS, JS, Images & Assets...</i>",
        parse_mode=ParseMode.HTML
    )

    download_path = None
    start_time = asyncio.get_event_loop().time()

    try:
        api_url = f"{A360APIBASEURL}/web/source?url={url}"
        
        timeout = aiohttp.ClientTimeout(total=120, connect=20, sock_read=60)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            await SmartAIO.edit_message_text(
                chat_id=message.chat.id,
                message_id=loading_message.message_id,
                text="<b>🔄 Processing request...</b>\n<i>Fetching website resources from API...</i>",
                parse_mode=ParseMode.HTML
            )
            
            async with session.get(api_url) as response:
                if response.status != 200:
                    error_text = await response.text()
                    await SmartAIO.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=loading_message.message_id,
                        text=f"<b>❌ API request failed.</b>\n<code>{html.escape(error_text)}</code>",
                        parse_mode=ParseMode.HTML
                    )
                    return
                
                api_data = await response.json()
                
                if not api_data.get('success'):
                    await SmartAIO.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=loading_message.message_id,
                        text="<b>❌ Failed to download source code.</b>\n<code>API returned unsuccessful response</code>",
                        parse_mode=ParseMode.HTML
                    )
                    return
                
                download_url = api_data.get('download_url')
                domain = api_data.get('domain')
                file_size_mb = api_data.get('file_size_mb')
                file_count = api_data.get('file_count')
                time_taken = api_data.get('time_taken_seconds')
                
                if not download_url:
                    await SmartAIO.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=loading_message.message_id,
                        text="<b>❌ Failed to get download URL from API.</b>",
                        parse_mode=ParseMode.HTML
                    )
                    return
                
                await SmartAIO.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=loading_message.message_id,
                    text="<b>📦 Downloading archive...</b>",
                    parse_mode=ParseMode.HTML
                )
                
                download_dir = os.path.join("downloads", f"ws_{message.chat.id}_{message.message_id}")
                os.makedirs(download_dir, exist_ok=True)
                
                domain_clean = domain.replace('www.', '') if domain else 'website'
                download_path = os.path.join(download_dir, f"SmartSourceCode({domain_clean}).zip")
                
                async with session.get(download_url) as dl_response:
                    if dl_response.status != 200:
                        await SmartAIO.edit_message_text(
                            chat_id=message.chat.id,
                            message_id=loading_message.message_id,
                            text="<b>❌ Failed to download the archive.</b>",
                            parse_mode=ParseMode.HTML
                        )
                        return
                    
                    with open(download_path, 'wb') as f:
                        async for chunk in dl_response.content.iter_chunked(8192):
                            f.write(chunk)
                
                end_time = asyncio.get_event_loop().time()
                total_time = end_time - start_time
                
                user = message.from_user
                first_name = html.escape(user.first_name)
                last_name = html.escape(user.last_name) if user.last_name else ''
                user_mention = f"<a href=\"tg://user?id={user.id}\">{first_name} {last_name}</a>".strip()
                
                caption = (
                    "<b>Website Source Download Successful ➺ ✅</b>\n"
                    "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                    f"<b>⊗ Website:</b> <code>{html.escape(domain)}</code>\n"
                    f"<b>⊗ Total Files:</b> <code>{file_count}</code>\n"
                    f"<b>⊗ Archive Size:</b> <code>{file_size_mb:.2f} MB</code>\n"
                    f"<b>⊗ File Contains:</b> <i>HTML, CSS, JS, Images, Fonts & Assets</i>\n"
                    f"<b>⊗ Time Taken:</b> <code>{total_time:.2f}s</code>\n"
                    "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                    f"<b>Downloaded By:</b> {user_mention}"
                )
                
                await delete_messages(chat_id=message.chat.id, message_ids=loading_message.message_id)
                
                await SmartAIO.send_document(
                    chat_id=message.chat.id,
                    document=FSInputFile(download_path, filename=f"SmartSourceCode({html.escape(domain_clean)}).zip"),
                    caption=caption,
                    parse_mode=ParseMode.HTML
                )
                
                if download_path and os.path.exists(download_path):
                    clean_download(download_path)
                if os.path.exists(download_dir):
                    clean_download(download_dir)

    except aiohttp.ClientError as e:
        try:
            await SmartAIO.edit_message_text(
                chat_id=message.chat.id,
                message_id=loading_message.message_id,
                text=f"<b>❌ Network error occurred.</b>\n<code>{html.escape(str(e))}</code>",
                parse_mode=ParseMode.HTML
            )
        except:
            pass
        await Smart_Notify(bot, "/ws", e, message)
    except Exception as e:
        try:
            await SmartAIO.edit_message_text(
                chat_id=message.chat.id,
                message_id=loading_message.message_id,
                text="<b>❌ An unexpected error occurred. Please try again later.</b>",
                parse_mode=ParseMode.HTML
            )
        except:
            pass
        await Smart_Notify(bot, "/ws", e, message)
    finally:
        if download_path and os.path.exists(download_path):
            try:
                clean_download(download_path)
            except:
                pass
        download_dir = os.path.join("downloads", f"ws_{message.chat.id}_{message.message_id}")
        if os.path.exists(download_dir):
            try:
                clean_download(download_dir)
            except:
                pass