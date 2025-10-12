import os
import asyncio
from datetime import datetime
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, FSInputFile
from pyrogram.enums import ParseMode as SmartParseMode
from bot import dp, SmartPyro
from bot.helpers.botutils import send_message, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.buttons import SmartButtons
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.guard import admin_only
from bot.core.database import SmartGuards
from config import UPDATE_CHANNEL_URL, OWNER_ID
from bot.helpers.graph import SmartGraph

smart_graph = SmartGraph()

try:
    loop = asyncio.get_event_loop()
    if loop.is_running():
        loop.create_task(smart_graph.initialize())
    else:
        loop.run_until_complete(smart_graph.initialize())
except Exception as e:
    LOGGER.error(f"Failed to create or access Telegraph account: {e}")

def validate_message(func):
    async def wrapper(message: Message, bot: Bot):
        if not message or not message.from_user:
            LOGGER.error("Invalid message received")
            return
        return await func(message, bot)
    return wrapper

async def create_telegraph_page(content: str) -> list:
    try:
        truncated_content = content[:40000]
        max_size_bytes = 20 * 1024
        pages = []
        page_content = ""
        current_size = 0
        lines = truncated_content.splitlines(keepends=True)

        for line in lines:
            line_bytes = line.encode('utf-8', errors='ignore')
            if current_size + len(line_bytes) > max_size_bytes and page_content:
                page_url = await smart_graph.create_page(
                    title="SmartLogs",
                    content=page_content,
                    author_name="SmartUtilBot",
                    author_url="https://t.me/TheSmartDevs"
                )
                if not page_url:
                    return []
                pages.append(page_url)
                page_content = ""
                current_size = 0
                await asyncio.sleep(0.5)

            page_content += line
            current_size += len(line_bytes)

        if page_content:
            page_url = await smart_graph.create_page(
                title="SmartLogs",
                content=page_content,
                author_name="SmartUtilBot",
                author_url="https://t.me/TheSmartDevs"
            )
            if not page_url:
                return []
            pages.append(page_url)
            await asyncio.sleep(0.5)

        return pages
    except Exception as e:
        LOGGER.error(f"Failed to create Telegraph page: {e}")
        return []

@dp.message(Command(commands=["logs"], prefix=BotCommands))
@validate_message
@admin_only
async def logs_command(message: Message, bot: Bot):
    try:
        loading_message = await send_message(
            chat_id=message.chat.id,
            text="<b>Checking The Logs...💥</b>",
            parse_mode=SmartParseMode.HTML
        )

        await asyncio.sleep(2)

        if not os.path.exists("botlog.txt"):
            if loading_message:
                try:
                    await bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=loading_message.message_id,
                        text="<b>Sorry, No Logs Found ❌</b>",
                        parse_mode=SmartParseMode.HTML
                    )
                    await asyncio.sleep(2)
                    await bot.delete_message(chat_id=message.chat.id, message_id=loading_message.message_id)
                except Exception as e:
                    LOGGER.error(f"Error handling no logs found: {e}")
            return

        LOGGER.info(f"User {message.from_user.id} is admin, sending log document")

        try:
            file_size_bytes = os.path.getsize("botlog.txt")
            file_size_kb = file_size_bytes / 1024

            with open("botlog.txt", "r", encoding="utf-8", errors="ignore") as f:
                line_count = sum(1 for _ in f)

            now = datetime.now()
            time_str = now.strftime("%H-%M-%S")
            date_str = now.strftime("%Y-%m-%d")

            caption_text = (
                "<b>Smart Logs Check → Successful ✅</b>\n"
                "<b>━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>⊗ File Size:</b> {file_size_kb:.2f} KB\n"
                f"<b>⊗ Logs Lines:</b> {line_count} Lines\n"
                f"<b>⊗ Time:</b> {time_str}\n"
                f"<b>⊗ Date:</b> {date_str}\n"
                "<b>━━━━━━━━━━━━━━━━━</b>\n"
                "<b>Smart LogsChecker → Activated ✅</b>"
            )

            buttons = SmartButtons()
            buttons.button(text="Display Logs", callback_data="display_logs")
            buttons.button(text="Web Paste", callback_data="web_paste")
            buttons.button(text="❌ Close", callback_data="close_doc", position="footer")
            reply_markup = buttons.build_menu(b_cols=2, f_cols=1)

            log_file = FSInputFile("botlog.txt")
            response = await bot.send_document(
                chat_id=message.chat.id,
                document=log_file,
                caption=caption_text,
                parse_mode=SmartParseMode.HTML,
                reply_markup=reply_markup
            )

            await bot.delete_message(chat_id=message.chat.id, message_id=loading_message.message_id)
            LOGGER.info(f"Successfully sent logs document for user_id {message.from_user.id}")

        except Exception as e:
            LOGGER.error(f"Error sending log document: {e}")
            if loading_message:
                try:
                    await bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=loading_message.message_id,
                        text="<b>Sorry, Unable to Send Log Document ❌</b>",
                        parse_mode=SmartParseMode.HTML
                    )
                    await asyncio.sleep(2)
                    await bot.delete_message(chat_id=message.chat.id, message_id=loading_message.message_id)
                except Exception as edit_error:
                    LOGGER.error(f"Error editing loading message: {edit_error}")

    except Exception as e:
        await Smart_Notify(bot, "logs_command", e, message)
        LOGGER.error(f"Failed to handle logs command for user_id {message.from_user.id}: {e}")
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Failed to process logs command!</b>",
            parse_mode=SmartParseMode.HTML
        )

@dp.callback_query(lambda c: c.data in ["close_doc", "close_logs", "web_paste", "display_logs"])
async def handle_logs_callback(query: CallbackQuery, bot: Bot):
    user_id = query.from_user.id
    auth_admins_data = await SmartGuards.find({}, {"user_id": 1, "_id": 0}).to_list(None)
    AUTH_ADMIN_IDS = [admin["user_id"] for admin in auth_admins_data]

    if user_id != OWNER_ID and user_id not in AUTH_ADMIN_IDS:
        LOGGER.info(f"Unauthorized logs callback attempt by user_id {user_id}")
        return

    data = query.data
    LOGGER.info(f"Logs callback query from user {user_id}, data: {data}")

    try:
        if data == "close_doc":
            await query.message.delete()
            await query.answer()

        elif data == "close_logs":
            await query.message.delete()
            await query.answer()

        elif data == "web_paste":
            await query.answer("Uploading logs to Telegraph...")

            try:
                await query.message.edit_caption(
                    caption="<b>Uploading SmartLogs To Telegraph✅</b>",
                    parse_mode=SmartParseMode.HTML
                )
            except Exception as e:
                LOGGER.error(f"Error editing caption for telegraph upload: {e}")

            if not os.path.exists("botlog.txt"):
                try:
                    await query.message.edit_caption(
                        caption="<b>Sorry, No Logs Found ❌</b>",
                        parse_mode=SmartParseMode.HTML
                    )
                except Exception as e:
                    LOGGER.error(f"Error editing caption for no logs: {e}")
                await query.answer()
                return

            try:
                with open("botlog.txt", "r", encoding="utf-8", errors="ignore") as f:
                    logs_content = f.read()

                telegraph_urls = await create_telegraph_page(logs_content)

                if telegraph_urls:
                    buttons = SmartButtons()

                    for i in range(0, len(telegraph_urls), 2):
                        buttons.button(text=f"View Web Part {i+1}", url=telegraph_urls[i])
                        if i + 1 < len(telegraph_urls):
                            buttons.button(text=f"View Web Part {i+2}", url=telegraph_urls[i+1])

                    buttons.button(text="❌ Close", callback_data="close_doc", position="footer")
                    reply_markup = buttons.build_menu(b_cols=2, f_cols=1)

                    file_size_bytes = os.path.getsize("botlog.txt")
                    file_size_kb = file_size_bytes / 1024

                    with open("botlog.txt", "r", encoding="utf-8", errors="ignore") as f:
                        line_count = sum(1 for _ in f)

                    now = datetime.now()
                    time_str = now.strftime("%H-%M-%S")
                    date_str = now.strftime("%Y-%m-%d")

                    caption_text = (
                        "<b>Smart Logs Check → Successful ✅</b>\n"
                        "<b>━━━━━━━━━━━━━━━━━</b>\n"
                        f"<b>⊗ File Size:</b> {file_size_kb:.2f} KB\n"
                        f"<b>⊗ Logs Lines:</b> {line_count} Lines\n"
                        f"<b>⊗ Time:</b> {time_str}\n"
                        f"<b>⊗ Date:</b> {date_str}\n"
                        "<b>━━━━━━━━━━━━━━━━━</b>\n"
                        "<b>Smart LogsChecker → Activated ✅</b>"
                    )

                    await query.message.edit_caption(
                        caption=caption_text,
                        parse_mode=SmartParseMode.HTML,
                        reply_markup=reply_markup
                    )
                else:
                    await query.message.edit_caption(
                        caption="<b>Sorry Failed To Upload On Telegraph</b>",
                        parse_mode=SmartParseMode.HTML
                    )

            except Exception as e:
                LOGGER.error(f"Error uploading to Telegraph: {e}")
                await query.message.edit_caption(
                    caption="<b>Sorry Failed To Upload On Telegraph</b>",
                    parse_mode=SmartParseMode.HTML
                )

        elif data == "display_logs":
            await send_logs_page(bot, query.message.chat.id)
            await query.answer()

    except Exception as e:
        await Smart_Notify(bot, "handle_logs_callback", e)
        LOGGER.error(f"Failed to handle logs callback for user_id {user_id}: {e}")
        await query.answer("❌ Failed to process callback!", show_alert=True)

async def send_logs_page(bot: Bot, chat_id: int):
    LOGGER.info(f"Sending latest logs to chat {chat_id}")

    if not os.path.exists("botlog.txt"):
        await send_message(
            chat_id=chat_id,
            text="<b>Sorry, No Logs Found ❌</b>",
            parse_mode=SmartParseMode.HTML
        )
        return

    try:
        with open("botlog.txt", "r", encoding="utf-8", errors="ignore") as f:
            logs = f.readlines()

        latest_logs = logs[-20:] if len(logs) > 20 else logs
        text = "".join(latest_logs)

        if len(text) > 4096:
            text = text[-4096:]

        buttons = SmartButtons()
        buttons.button(text="🔙 Back", callback_data="close_logs")
        reply_markup = buttons.build_menu(b_cols=1)

        await send_message(
            chat_id=chat_id,
            text=text if text else "No logs available.❌",
            reply_markup=reply_markup
        )

    except Exception as e:
        LOGGER.error(f"Error sending logs: {e}")
        await send_message(
            chat_id=chat_id,
            text="<b>Sorry, There Was an Issue on the Server ❌</b>",
            parse_mode=SmartParseMode.HTML
        )