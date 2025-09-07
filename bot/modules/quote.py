# Copyright @ISmartCoder
# SmartUtilBot - Telegram Utility Bot for Smart Features Bot
# Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack>
import aiohttp
import asyncio
import base64
import aiofiles
import os
from PIL import Image
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.enums import ParseMode, ChatType, ChatAction, MessageEntityType
from bot import dp, SmartAIO
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.notify import Smart_Notify
from bot.helpers.logger import LOGGER
from bot.helpers.commands import BotCommands
from bot.helpers.defend import SmartDefender
from config import IMAGE_UPLOAD_KEY
logger = LOGGER
MAX_CONCURRENT_TASKS = 5
semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

async def download_default_avatar(url, session):
    async with semaphore:
        if "t.me/" in url:
            return None
        try:
            async with session.get(url) as response:
                if response.status == 200:
                    temp_file = f"default_avatar_{os.urandom(4).hex()}.jpg"
                    content = await response.read()
                    async with aiofiles.open(temp_file, 'wb') as f:
                        await f.write(content)
                    return temp_file
                return None
        except Exception as e:
            logger.error(f"Error downloading default avatar: {e}")
            return None

async def upload_to_imgbb(image_path, session):
    try:
        async with semaphore:
            async with aiofiles.open(image_path, "rb") as file:
                image_data = base64.b64encode(await file.read()).decode('utf-8')
            upload_url = "https://api.imgbb.com/1/upload"
            payload = {"key": IMAGE_UPLOAD_KEY, "image": image_data}
            async with session.post(upload_url, data=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("success"):
                        return result["data"]["url"]
                return None
    except Exception as e:
        logger.error(f"Failed to upload image to ImgBB: {e}")
        return None

async def convert_photo_to_sticker(photo_path):
    try:
        async with semaphore:
            img = Image.open(photo_path)
            img.thumbnail((512, 512), Image.Resampling.LANCZOS)
            square_size = max(img.size)
            sticker = Image.new('RGBA', (square_size, square_size), (0, 0, 0, 0))
            offset = ((square_size - img.size[0]) // 2, (square_size - img.size[1]) // 2)
            sticker.paste(img, offset)
            sticker_path = f"sticker_{os.urandom(4).hex()}.webp"
            sticker.save(sticker_path, 'WEBP', quality=85)
            img.close()
            return sticker_path
    except Exception as e:
        logger.error(f"Failed to convert photo to sticker: {e}")
        return None

async def convert_sticker_to_image(sticker_path):
    try:
        async with semaphore:
            img = Image.open(sticker_path)
            img.thumbnail((512, 512), Image.Resampling.LANCZOS)
            photo_path = f"converted_{os.urandom(4).hex()}.jpg"
            img.convert('RGB').save(photo_path, "JPEG")
            img.close()
            return photo_path
    except Exception as e:
        logger.error(f"Failed to convert sticker: {e}")
        return None

async def get_emoji_status(bot: Bot, user_id):
    try:
        async with semaphore:
            user = await bot.get_chat(user_id)
            if hasattr(user, 'emoji_status_custom_emoji_id') and user.emoji_status_custom_emoji_id:
                return str(user.emoji_status_custom_emoji_id)
            return None
    except Exception as e:
        logger.error(f"Failed to fetch emoji status for user {user_id}: {e}")
        return None

async def extract_premium_emojis(message, offset_adjust=0):
    premium_emoji_entities = []
    if message.entities:
        for entity in message.entities:
            if entity.type == MessageEntityType.CUSTOM_EMOJI and hasattr(entity, 'custom_emoji_id') and entity.custom_emoji_id:
                entity_data = {
                    "type": "custom_emoji",
                    "offset": entity.offset - offset_adjust,
                    "length": entity.length,
                    "document_id": str(entity.custom_emoji_id)
                }
                premium_emoji_entities.append(entity_data)
    if message.caption_entities:
        for entity in message.caption_entities:
            if entity.type == MessageEntityType.CUSTOM_EMOJI and hasattr(entity, 'custom_emoji_id') and entity.custom_emoji_id:
                entity_data = {
                    "type": "custom_emoji",
                    "offset": entity.offset - offset_adjust,
                    "length": entity.length,
                    "document_id": str(entity.custom_emoji_id)
                }
                premium_emoji_entities.append(entity_data)
    return premium_emoji_entities

async def extract_message_entities(message, skip_command_prefix=False, command_prefix_length=0):
    entities = []
    def process_entity(entity, is_caption=False):
        adjusted_offset = entity.offset - (command_prefix_length if skip_command_prefix else 0)
        if skip_command_prefix and entity.offset < command_prefix_length:
            return None
        
        entity_type_str = ""
        if isinstance(entity.type, str):
            entity_type_str = entity.type
        else:
            try:
                if hasattr(entity.type, 'value'):
                    entity_type_str = entity.type.value
                elif hasattr(entity.type, 'name'):
                    entity_type_str = entity.type.name.lower()
                else:
                    entity_type_str = str(entity.type).lower()
            except:
                entity_type_str = str(entity.type).lower()
        
        entity_data = {"type": entity_type_str, "offset": adjusted_offset, "length": entity.length}
        
        if entity.type == MessageEntityType.CUSTOM_EMOJI and hasattr(entity, 'custom_emoji_id') and entity.custom_emoji_id:
            entity_data["type"] = "custom_emoji"
            entity_data["document_id"] = str(entity.custom_emoji_id)
        
        for attr in ['url', 'user', 'language']:
            if hasattr(entity, attr) and getattr(entity, attr):
                attr_value = getattr(entity, attr)
                if attr == 'user' and hasattr(attr_value, 'id'):
                    entity_data[attr] = str(attr_value.id)
                else:
                    entity_data[attr] = attr_value
        return entity_data
    
    if message.entities:
        for entity in message.entities:
            entity_data = process_entity(entity)
            if entity_data:
                entities.append(entity_data)
    if message.caption_entities:
        for entity in message.caption_entities:
            entity_data = process_entity(entity, is_caption=True)
            if entity_data:
                entities.append(entity_data)
    return entities

@dp.message(Command(commands=["q"], prefix=BotCommands))
@new_task
@SmartDefender
async def q_command(message: Message, bot: Bot):
    if message.chat.type not in [ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP]:
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ This command only works in private or group chats</b>",
            parse_mode=ParseMode.HTML
        )
        return
    
    user_id = message.from_user.id
    logger.info(f"Command received from user {user_id} in chat {message.chat.id}: {message.text}")
    
    async with aiohttp.ClientSession() as session:
        avatar_file_path = None
        photo_path = None
        sticker_path = None
        try:
            await bot.send_chat_action(message.chat.id, action=ChatAction.CHOOSE_STICKER)
            command_parts = get_args(message)
            replied_message = message.reply_to_message
            text = None
            user = None
            user_id = None
            full_name = None
            message_entities = []
            
            async with semaphore:
                if replied_message and not command_parts and (replied_message.text or replied_message.photo or replied_message.sticker or replied_message.video or replied_message.animation):
                    if hasattr(replied_message, 'forward_origin') and replied_message.forward_origin:
                        if hasattr(replied_message.forward_origin, 'sender_user') and replied_message.forward_origin.sender_user:
                            user = replied_message.forward_origin.sender_user
                        elif hasattr(replied_message.forward_origin, 'sender_user_name') and replied_message.forward_origin.sender_user_name:
                            full_name = replied_message.forward_origin.sender_user_name
                            user_id = None
                        elif hasattr(replied_message.forward_origin, 'sender_chat') and replied_message.forward_origin.sender_chat:
                            full_name = replied_message.forward_origin.sender_chat.title
                            user_id = replied_message.forward_origin.sender_chat.id
                        else:
                            user = replied_message.from_user
                    else:
                        user = replied_message.from_user
                elif replied_message and command_parts:
                    if hasattr(replied_message, 'forward_origin') and replied_message.forward_origin:
                        if hasattr(replied_message.forward_origin, 'sender_user') and replied_message.forward_origin.sender_user:
                            user = replied_message.forward_origin.sender_user
                        elif hasattr(replied_message.forward_origin, 'sender_user_name') and replied_message.forward_origin.sender_user_name:
                            full_name = replied_message.forward_origin.sender_user_name
                            user_id = None
                        elif hasattr(replied_message.forward_origin, 'sender_chat') and replied_message.forward_origin.sender_chat:
                            full_name = replied_message.forward_origin.sender_chat.title
                            user_id = replied_message.forward_origin.sender_chat.id
                        else:
                            user = replied_message.from_user
                    else:
                        user = replied_message.from_user
                    text = " ".join(command_parts)
                elif command_parts:
                    user = message.from_user
                    text = " ".join(command_parts)
                
                if user:
                    full_name = user.first_name
                    if user.last_name:
                        full_name += f" {user.last_name}"
                    user_id = user.id
                    photos = await bot.get_user_profile_photos(user.id, limit=1)
                    if photos.photos:
                        file_id = photos.photos[0][-1].file_id
                        avatar_file_path = f"avatar_{os.urandom(4).hex()}.jpg"
                        await bot.download(file=file_id, destination=avatar_file_path)
                elif message.chat.type in [ChatType.SUPERGROUP, ChatType.GROUP]:
                    full_name = message.chat.title
                    user_id = message.chat.id
                    chat = await bot.get_chat(message.chat.id)
                    if chat.photo:
                        file_id = chat.photo.big_file_id
                        avatar_file_path = f"avatar_{os.urandom(4).hex()}.jpg"
                        await bot.download(file=file_id, destination=avatar_file_path)
                
                avatar_base64 = None
                if avatar_file_path:
                    async with aiofiles.open(avatar_file_path, "rb") as file:
                        avatar_data = await file.read()
                    avatar_base64 = base64.b64encode(avatar_data).decode()
                
                font_size = "small"
                
                emoji_status_id = await get_emoji_status(bot, user_id) if user_id and user_id > 0 else None
                
                from_payload = {
                    "id": str(user_id) if user_id else "0",
                    "name": full_name or "Anonymous",
                    "fontSize": font_size
                }
                
                if avatar_base64 and user_id:
                    from_payload["photo"] = {"url": f"data:image/jpeg;base64,{avatar_base64}"}
                
                if emoji_status_id and user_id:
                    from_payload["emoji_status"] = emoji_status_id
                
                if replied_message and not command_parts and (replied_message.photo or replied_message.sticker or replied_message.video or replied_message.animation):
                    is_photo = replied_message.photo is not None
                    is_sticker = replied_message.sticker is not None
                    is_video = replied_message.video is not None
                    is_animation = replied_message.animation is not None
                    
                    try:
                        if is_photo:
                            file_id = replied_message.photo[-1].file_id
                            photo_path = f"photo_{os.urandom(4).hex()}.jpg"
                            await bot.download(file=file_id, destination=photo_path)
                        elif is_sticker:
                            if replied_message.sticker.is_animated or replied_message.sticker.is_video:
                                if not replied_message.sticker.thumbnail:
                                    await send_message(
                                        chat_id=message.chat.id,
                                        text="<b>❌ Sticker has no thumbnail.</b>",
                                        parse_mode=ParseMode.HTML
                                    )
                                    return
                                file_id = replied_message.sticker.thumbnail.file_id
                                sticker_path = f"sticker_{os.urandom(4).hex()}.jpg"
                                await bot.download(file=file_id, destination=sticker_path)
                            else:
                                file_id = replied_message.sticker.file_id
                                sticker_path = f"sticker_{os.urandom(4).hex()}.webp"
                                await bot.download(file=file_id, destination=sticker_path)
                            photo_path = await convert_sticker_to_image(sticker_path)
                        elif is_video or is_animation:
                            media = replied_message.video if is_video else replied_message.animation
                            if not media.thumbnail:
                                await send_message(
                                    chat_id=message.chat.id,
                                    text="<b>❌ Media has no thumbnail.</b>",
                                    parse_mode=ParseMode.HTML
                                )
                                return
                            file_id = media.thumbnail.file_id
                            photo_path = f"thumb_{os.urandom(4).hex()}.jpg"
                            await bot.download(file=file_id, destination=photo_path)
                        
                        if not photo_path:
                            logger.error("Failed to download replied media")
                            await send_message(
                                chat_id=message.chat.id,
                                text="<b>❌ Failed To Generate Sticker</b>",
                                parse_mode=ParseMode.HTML
                            )
                            return
                        
                        hosted_url = await upload_to_imgbb(photo_path, session)
                        if not hosted_url:
                            async with aiofiles.open(photo_path, "rb") as file:
                                content = await file.read()
                            photo_base64 = base64.b64encode(content).decode()
                            hosted_url = f"data:image/jpeg;base64,{photo_base64}"
                        
                        text = replied_message.caption if replied_message.caption else ""
                        message_entities = await extract_message_entities(replied_message)
                        premium_emojis = await extract_premium_emojis(replied_message)
                        
                        if premium_emojis:
                            existing_offsets = [e['offset'] for e in message_entities if e.get("type") == "custom_emoji"]
                            for emoji in premium_emojis:
                                if emoji['offset'] not in existing_offsets:
                                    message_entities.append(emoji)
                        
                        json_data = {
                            "type": "quote",
                            "format": "webp",
                            "backgroundColor": "#000000",
                            "width": 512,
                            "height": 768,
                            "scale": 2,
                            "messages": [
                                {
                                    "entities": message_entities,
                                    "avatar": bool(avatar_base64 and user_id),
                                    "from": from_payload,
                                    "media": {"type": "photo", "url": hosted_url},
                                    "text": text,
                                    "textFontSize": font_size
                                }
                            ]
                        }
                        
                        async with semaphore:
                            async with session.post('https://bot.lyo.su/quote/generate', json=json_data) as response:
                                if response.status != 200:
                                    logger.error(f"Quotly API error: {response.status} - {await response.text()}")
                                    raise Exception(f"API returned status code {response.status}")
                                response_json = await response.json()
                                if 'result' not in response_json or 'image' not in response_json['result']:
                                    logger.error(f"Invalid response from API: {response_json}")
                                    raise Exception("Invalid response from API")
                        
                        async with semaphore:
                            buffer = base64.b64decode(response_json['result']['image'].encode('utf-8'))
                            file_path = 'Quotly.webp'
                            async with aiofiles.open(file_path, 'wb') as f:
                                await f.write(buffer)
                            try:
                                await bot.send_sticker(
                                    chat_id=message.chat.id,
                                    sticker=FSInputFile(file_path),
                                    emoji="😀"
                                )
                                logger.info("Sticker sent successfully")
                            except Exception as e:
                                logger.error(f"Failed to send sticker: {e}")
                                raise
                    except Exception as e:
                        logger.error(f"Error creating sticker from media: {e}")
                        await send_message(
                            chat_id=message.chat.id,
                            text="<b>❌ Failed To Generate Sticker</b>",
                            parse_mode=ParseMode.HTML
                        )
                    finally:
                        async with semaphore:
                            if avatar_file_path and os.path.exists(avatar_file_path):
                                clean_download(avatar_file_path)
                            if photo_path and os.path.exists(photo_path):
                                clean_download(photo_path)
                            if sticker_path and os.path.exists(sticker_path):
                                clean_download(sticker_path)
                            if os.path.exists('Quotly.webp'):
                                clean_download('Quotly.webp')
                    return
                
                if replied_message and not command_parts:
                    if replied_message.text or replied_message.caption:
                        text = replied_message.text or replied_message.caption
                        message_entities = await extract_message_entities(replied_message)
                        premium_emojis = await extract_premium_emojis(replied_message)
                        
                        if premium_emojis:
                            existing_offsets = [e['offset'] for e in message_entities if e.get("type") == "custom_emoji"]
                            for emoji in premium_emojis:
                                if emoji['offset'] not in existing_offsets:
                                    message_entities.append(emoji)
                    else:
                        await send_message(
                            chat_id=message.chat.id,
                            text="<b>Please send text, a sticker, a photo, a video, or a GIF to create your sticker.</b>",
                            parse_mode=ParseMode.HTML
                        )
                        return
                elif command_parts:
                    message_entities = await extract_message_entities(message, skip_command_prefix=True, command_prefix_length=len(message.text.split()[0]) + 1)
                    premium_emojis = await extract_premium_emojis(message, offset_adjust=len(message.text.split()[0]) + 1)
                    
                    if premium_emojis:
                        existing_offsets = [e['offset'] for e in message_entities if e.get("type") == "custom_emoji"]
                        for emoji in premium_emojis:
                            if emoji['offset'] not in existing_offsets:
                                message_entities.append(emoji)
                else:
                    await send_message(
                        chat_id=message.chat.id,
                        text="<b>Please send text, a sticker, a photo, a video, or a GIF to create your sticker.</b>",
                        parse_mode=ParseMode.HTML
                    )
                    return
                
                if message_entities:
                    for i, entity in enumerate(message_entities, 1):
                        if entity.get("type") == "custom_emoji" and "document_id" not in entity:
                            logger.error(f"Premium emoji {i} is missing document_id!")
                
                json_data = {
                    "type": "quote",
                    "format": "webp",
                    "backgroundColor": "#000000",
                    "width": 512,
                    "height": 768,
                    "scale": 2,
                    "messages": [
                        {
                            "entities": message_entities,
                            "avatar": bool(avatar_base64 and user_id),
                            "from": from_payload,
                            "text": text or "",
                            "textFontSize": font_size,
                            "replyMessage": {}
                        }
                    ]
                }
                
                async with semaphore:
                    async with session.post('https://bot.lyo.su/quote/generate', json=json_data) as response:
                        if response.status != 200:
                            logger.error(f"Quotly API error: {response.status} - {await response.text()}")
                            raise Exception(f"API returned status code {response.status}")
                        response_json = await response.json()
                        if 'result' not in response_json or 'image' not in response_json['result']:
                            logger.error(f"Invalid response from API: {response_json}")
                            raise Exception("Invalid response from API")
                
                async with semaphore:
                    buffer = base64.b64decode(response_json['result']['image'].encode('utf-8'))
                    file_path = 'Quotly.webp'
                    async with aiofiles.open(file_path, 'wb') as f:
                        await f.write(buffer)
                    try:
                        await bot.send_sticker(
                            chat_id=message.chat.id,
                            sticker=FSInputFile(file_path),
                            emoji="😀"
                        )
                        logger.info("Sticker sent successfully")
                    except Exception as e:
                        logger.error(f"Failed to send sticker: {e}")
                        raise
                        
        except Exception as e:
            logger.error(f"Error generating quote: {e}")
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Failed To Generate Sticker</b>",
                parse_mode=ParseMode.HTML
            )
            await Smart_Notify(bot, "/q", e, message)
        finally:
            async with semaphore:
                if avatar_file_path and os.path.exists(avatar_file_path):
                    clean_download(avatar_file_path)
                if photo_path and os.path.exists(photo_path):
                    clean_download(photo_path)
                if sticker_path and os.path.exists(sticker_path):
                    clean_download(sticker_path)
                if os.path.exists('Quotly.webp'):
                    clean_download('Quotly.webp')