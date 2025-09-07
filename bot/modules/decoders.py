# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
#  Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
import os
import asyncio
import base64
import binascii
from aiogram import Bot
from aiogram.filters import Command, BaseFilter
from aiogram.types import Message, FSInputFile
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from bot import dp
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.defend import SmartDefender
from config import COMMAND_PREFIX, MAX_TXT_SIZE

commands = {
    "b64en": lambda text: base64.b64encode(text.encode()).decode(),
    "b64de": lambda text: base64.b64decode(text).decode(),
    "b32en": lambda text: base64.b32encode(text.encode()).decode(),
    "b32de": lambda text: base64.b32decode(text).decode(),
    "binen": lambda text: ' '.join(format(ord(char), '08b') for char in text),
    "binde": lambda text: ''.join(chr(int(b, 2)) for b in text.split()),
    "hexen": lambda text: binascii.hexlify(text.encode()).decode(),
    "hexde": lambda text: binascii.unhexlify(text).decode(),
    "octen": lambda text: ' '.join(format(ord(char), '03o') for char in text),
    "octde": lambda text: ''.join(chr(int(o, 8)) for o in text.split()),
    "trev": lambda text: text[::-1],
    "tcap": lambda text: text.upper(),
    "tsm": lambda text: text.lower(),
    "wc": lambda text: (
        "<b>📊 Text Counter</b>\n\n" +
        "<b>✅ Words:</b> <code>" + str(len(text.split())) + "</code>\n" +
        "<b>✅ Characters:</b> <code>" + str(len(text)) + "</code>\n" +
        "<b>✅ Sentences:</b> <code>" + str(text.count('.') + text.count('!') + text.count('?')) + "</code>\n" +
        "<b>✅ Paragraphs:</b> <code>" + str(text.count('\n') + 1) + "</code>"
    )
}

class DecoderCommandFilter(BaseFilter):
    async def __call__(self, message: Message):
        if not message.text:
            return False
        return message.text.split()[0][1:] in commands
        
@dp.message(DecoderCommandFilter())
@new_task
@SmartDefender
async def handle_command(message: Message, bot: Bot):
    file_path = None
    file_name = None
    try:
        command = message.text.split()[0][1:]
        func = commands[command]
        processing_msg = await send_message(
            chat_id=message.chat.id,
            text="<b>Processing Your Input...✨</b>",
            parse_mode=ParseMode.HTML
        )
        text = None
        if message.reply_to_message:
            if message.reply_to_message.document:
                if message.reply_to_message.document.file_size > MAX_TXT_SIZE:
                    await send_message(
                        chat_id=message.chat.id,
                        text=f"<b>❌ File too large! Max size is {MAX_TXT_SIZE // 1024 // 1024}MB</b>",
                        parse_mode=ParseMode.HTML
                    )
                    await delete_messages(message.chat.id, [processing_msg.message_id])
                    LOGGER.warning(f"File too large for /{command} in chat {message.chat.id}")
                    return
                os.makedirs("./downloads", exist_ok=True)
                file_path = os.path.join("./downloads", message.reply_to_message.document.file_name or f"{command}_input.txt")
                await bot.download(message.reply_to_message.document, destination=file_path)
                with open(file_path, "r", encoding="utf-8") as file:
                    text = file.read()
            else:
                text = message.reply_to_message.text
        else:
            text = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else None
        if not text:
            await send_message(
                chat_id=message.chat.id,
                text="<b>⚠️ Please provide text or reply to a message/file❌</b>",
                parse_mode=ParseMode.HTML
            )
            await delete_messages(message.chat.id, [processing_msg.message_id])
            LOGGER.warning(f"No text provided for /{command} in chat {message.chat.id}")
            if file_path:
                clean_download(file_path)
            return
        result = func(text)
        user_full_name = message.from_user.first_name + (" " + message.from_user.last_name if message.from_user.last_name else "")
        user_mention = f"<a href='tg://user?id={message.from_user.id}'>{user_full_name}</a>"
        LOGGER.info(f"Processed /{command} in chat {message.chat.id}")
        if len(result) > 4096:
            os.makedirs("./downloads", exist_ok=True)
            file_name = os.path.join("./downloads", f"{command}_result.txt")
            with open(file_name, "w", encoding="utf-8") as file:
                file.write(result)
            await bot.send_document(
                chat_id=message.chat.id,
                document=FSInputFile(path=file_name),
                caption=(
                    f"✨ <b>Here is your processed file!</b> ✨\n\n"
                    f"📂 <b>Command Used:</b> <code>{command}</code>\n"
                    f"📝 <b>Requested By:</b> {user_mention}\n"
                    f"📜 <b>Processed Successfully!</b> ✅"
                ),
                parse_mode=ParseMode.HTML
            )
        else:
            await send_message(
                chat_id=message.chat.id,
                text=f"<b>✅ {command} Result:</b>\n<code>{result}</code>" if command != "wc" else result,
                parse_mode=ParseMode.HTML
            )
        await delete_messages(message.chat.id, [processing_msg.message_id])
        if file_path:
            clean_download(file_path)
        if file_name:
            clean_download(file_name)
    except (Exception, TelegramBadRequest) as e:
        await delete_messages(message.chat.id, [processing_msg.message_id])
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Sorry Bro, Invalid Text Provided!</b>",
            parse_mode=ParseMode.HTML
        )
        LOGGER.error(f"Error processing /{command} in chat {message.chat.id}: {str(e)}")
        await Smart_Notify(bot, f"/{command}", e, message)
        if file_path:
            clean_download(file_path)
        if file_name and os.path.exists(file_name):
            clean_download(file_name)