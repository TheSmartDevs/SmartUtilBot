from bot import SmartAIO
from bot.helpers.logger import LOGGER
from aiogram.types import Message
from aiogram.enums import ParseMode

async def send_message(chat_id, text, parse_mode=ParseMode.HTML, reply_markup=None, reply_to_message_id=None, disable_web_page_preview=False):
    try:
        return await SmartAIO.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            reply_to_message_id=reply_to_message_id,
            disable_web_page_preview=disable_web_page_preview
        )
    except Exception as e:
        LOGGER.error(f"Failed to send message to {chat_id}: {e}")
        return None

def get_args(message: Message):
    if not message.text:
        return []
    text = message.text.split(None, 1)
    if len(text) < 2:
        return []
    args = text[1].strip()
    if not args:
        return []
    result = []
    current = ""
    in_quotes = False
    quote_char = None
    i = 0
    while i < len(args):
        char = args[i]
        if char in ('"', "'") and (i == 0 or args[i-1] != '\\'):
            if in_quotes and char == quote_char:
                in_quotes = False
                quote_char = None
                if current:
                    result.append(current)
                    current = ""
            else:
                in_quotes = True
                quote_char = char
        elif char == ' ' and not in_quotes:
            if current:
                result.append(current)
                current = ""
        else:
            current += char
        i += 1
    if current:
        result.append(current)
    return result

async def delete_messages(chat_id, message_ids):
    try:
        if isinstance(message_ids, int):
            message_ids = [message_ids]
        await SmartAIO.delete_messages(chat_id=chat_id, message_ids=message_ids)
        LOGGER.info(f"Deleted messages {message_ids} in chat {chat_id}")
        return True
    except Exception as e:
        LOGGER.error(f"Failed to delete messages {message_ids} in chat {chat_id}: {e}")
        return False