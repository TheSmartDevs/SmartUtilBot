from bot import SmartAIO
from bot.helpers.logger import LOGGER
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove, ForceReply
from aiogram.types import MessageEntity, LinkPreviewOptions, ReplyParameters, SuggestedPostParameters

async def send_message(
    chat_id: int | str,
    text: str,
    parse_mode: str | None = ParseMode.HTML,
    reply_markup: InlineKeyboardMarkup | ReplyKeyboardMarkup | ReplyKeyboardRemove | ForceReply | None = None,
    reply_to_message_id: int | None = None,
    disable_web_page_preview: bool | None = False,
    business_connection_id: str | None = None,
    message_thread_id: int | None = None,
    direct_messages_topic_id: int | None = None,
    entities: list[MessageEntity] | None = None,
    link_preview_options: LinkPreviewOptions | None = None,
    disable_notification: bool | None = None,
    protect_content: bool | None = None,
    allow_paid_broadcast: bool | None = None,
    message_effect_id: str | None = None,
    suggested_post_parameters: SuggestedPostParameters | None = None,
    reply_parameters: ReplyParameters | None = None,
    allow_sending_without_reply: bool | None = None
):
    try:
        return await SmartAIO.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            reply_to_message_id=reply_to_message_id,
            disable_web_page_preview=disable_web_page_preview,
            business_connection_id=business_connection_id,
            message_thread_id=message_thread_id,
            direct_messages_topic_id=direct_messages_topic_id,
            entities=entities,
            link_preview_options=link_preview_options,
            disable_notification=disable_notification,
            protect_content=protect_content,
            allow_paid_broadcast=allow_paid_broadcast,
            message_effect_id=message_effect_id,
            suggested_post_parameters=suggested_post_parameters,
            reply_parameters=reply_parameters,
            allow_sending_without_reply=allow_sending_without_reply
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