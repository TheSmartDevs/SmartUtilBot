import re
import os
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from bot import dp
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.buttons import SmartButtons
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from config import MAX_TXT_SIZE, UPDATE_CHANNEL_URL

async def filter_bin(content, bin_number):
    filtered_lines = [line for line in content if line.startswith(bin_number)]
    return filtered_lines

async def remove_bin(content, bin_number):
    filtered_lines = [line for line in content if not line.startswith(bin_number)]
    return filtered_lines

async def process_file(file_path, bin_number, command):
    with open(file_path, 'r') as file:
        content = file.readlines()
    if command in ['/adbin', '.adbin']:
        return await filter_bin(content, bin_number)
    elif command in ['/rmbin', '.rmbin']:
        return await remove_bin(content, bin_number)

@dp.message(Command(commands=["adbin", "rmbin"], prefix=BotCommands))
@new_task
async def handle_bin_commands(message: Message, bot: Bot):
    progress_message = None
    try:
        args = get_args(message)
        if len(args) != 1:
            progress_message = await send_message(
                chat_id=message.chat.id,
                text="<b>⚠️ Please provide a valid BIN number❌</b>",
                parse_mode=ParseMode.HTML
            )
            return

        command = message.text.split()[0]
        bin_number = args[0]
        if not re.match(r'^\d{6}$', bin_number):
            progress_message = await send_message(
                chat_id=message.chat.id,
                text="<b>⚠️ BIN number must be 6 digits❌</b>",
                parse_mode=ParseMode.HTML
            )
            return

        if not message.reply_to_message or not message.reply_to_message.document or not message.reply_to_message.document.file_name.endswith('.txt'):
            progress_message = await send_message(
                chat_id=message.chat.id,
                text="<b>⚠️ Please provide a valid .txt file by replying to it.❌</b>",
                parse_mode=ParseMode.HTML
            )
            return

        file_size_mb = message.reply_to_message.document.file_size / (1024 * 1024)
        if file_size_mb > MAX_TXT_SIZE:
            progress_message = await send_message(
                chat_id=message.chat.id,
                text="<b>⚠️ File size exceeds the 15MB limit❌</b>",
                parse_mode=ParseMode.HTML
            )
            return

        processing_text = "<b>Adding Bins...</b>" if command in ['/adbin', '.adbin'] else "<b>Removing Bins...</b>"
        progress_message = await send_message(
            chat_id=message.chat.id,
            text=processing_text,
            parse_mode=ParseMode.HTML
        )

        file_id = message.reply_to_message.document.file_id
        file_info = await bot.get_file(file_id)
        file_path = f"downloads/{file_id}.txt"
        os.makedirs('downloads', exist_ok=True)
        await bot.download_file(file_info.file_path, file_path)
        processed_cards = await process_file(file_path, bin_number, command)

        if not processed_cards:
            await progress_message.edit_text(
                text=f"<b>❌ No credit card details found with BIN {bin_number}.</b>",
                parse_mode=ParseMode.HTML
            )
            clean_download()
            return

        action = "Add" if command in ['/adbin', '.adbin'] else "Remove"
        actioner = "Adder" if command in ['/adbin', '.adbin'] else "Remover"
        file_label = "Added" if command in ['/adbin', '.adbin'] else "Removed"

        await delete_messages(message.chat.id, progress_message.message_id)

        if len(processed_cards) <= 10:
            formatted_cards = "\n".join(f"<code>{line.strip()}</code>" for line in processed_cards)
            response_message = (
                f"<b>Smart Bin {action} → Successful ✅</b>\n"
                f"<b>━━━━━━━━━━━━━━━━━</b>\n"
                f"{formatted_cards}\n"
                f"<b>━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>Smart Bin {actioner} → Activated ✅</b>"
            )
            await send_message(
                chat_id=message.chat.id,
                text=response_message,
                parse_mode=ParseMode.HTML
            )
        else:
            file_name = f"downloads/Bin_{file_label}_Txt.txt"
            with open(file_name, "w") as file:
                file.write("".join(processed_cards))

            total_amount = len(processed_cards)
            total_size = f"{os.path.getsize(file_name) / 1024:.2f} KB"
            total_lines = len(processed_cards)
            caption = (
                f"<b>Smart Bin {action} → Successful ✅</b>\n"
                f"<b>━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>⊗ Total Amount:</b> {total_amount}\n"
                f"<b>⊗ Total Size:</b> {total_size}\n"
                f"<b>⊗ Target Bin:</b> {bin_number}\n"
                f"<b>⊗ Total Lines:</b> {total_lines}\n"
                f"<b>━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>Smart Bin {actioner} → Activated ✅</b>"
            )

            buttons = SmartButtons()
            buttons.button(text="Join For Updates", url=UPDATE_CHANNEL_URL)
            await bot.send_document(
                chat_id=message.chat.id,
                document=FSInputFile(path=file_name),
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=buttons.build_menu(b_cols=1)
            )
            os.remove(file_name)

        clean_download()

    except Exception as e:
        LOGGER.error(f"Error processing {command} command in chat {message.chat.id}: {str(e)}")
        await Smart_Notify(bot, command, e, message)
        if progress_message:
            try:
                await progress_message.edit_text(
                    text="<b>❌ Error processing file</b>",
                    parse_mode=ParseMode.HTML
                )
            except TelegramBadRequest:
                await send_message(
                    chat_id=message.chat.id,
                    text="<b>❌ Error processing file</b>",
                    parse_mode=ParseMode.HTML
                )
        else:
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Error processing file</b>",
                parse_mode=ParseMode.HTML
            )
        clean_download()