import os 
from datetime import datetime, timedelta 
from dateutil.relativedelta import relativedelta 
from aiogram import Bot 
from aiogram.filters import Command 
from aiogram.types import Message, FSInputFile 
from aiogram.enums import ParseMode
from pyrogram.enums import ChatType
from bot import dp, SmartAIO, SmartPyro, SmartUserBot 
from bot.helpers.utils import new_task 
from bot.helpers.botutils import send_message, delete_messages 
from bot.helpers.logger import LOGGER 
from bot.helpers.buttons import SmartButtons 
from bot.helpers.dcutil import SmartDCLocate 
from bot.helpers.commands import BotCommands 
from bot.helpers.notify import Smart_Notify 
from bot.helpers.defend import SmartDefender 
from pyrogram.errors import PeerIdInvalid, UsernameNotOccupied, ChannelInvalid 
from pyrogram.enums import UserStatus 
 
logger = LOGGER 
 
def calculate_account_age(creation_date): 
    today = datetime.now() 
    delta = relativedelta(today, creation_date) 
    years = delta.years 
    months = delta.months 
    days = delta.days 
    return f"{years} years, {months} months, {days} days" 
 
def estimate_account_creation_date(user_id): 
    reference_points = [ 
        (100000000, datetime(2013, 8, 1)), 
        (1273841502, datetime(2020, 8, 13)), 
        (1500000000, datetime(2021, 5, 1)), 
        (2000000000, datetime(2022, 12, 1)), 
    ] 
     
    closest_point = min(reference_points, key=lambda x: abs(x[0] - user_id)) 
    closest_user_id, closest_date = closest_point 
     
    id_difference = user_id - closest_user_id 
    days_difference = id_difference / 20000000 
    creation_date = closest_date + timedelta(days=days_difference) 
     
    return creation_date 
 
def get_status_display(status): 
    if not status: 
        return "Unknown" 
     
    status_map = { 
        UserStatus.ONLINE: "Online", 
        UserStatus.OFFLINE: "Offline",  
        UserStatus.RECENTLY: "Recently", 
        UserStatus.LAST_WEEK: "Last Week", 
        UserStatus.LAST_MONTH: "Last Month", 
        UserStatus.LONG_AGO: "Long Ago" 
    } 
    return status_map.get(status, "Unknown") 
 
def format_user_response(user, chat=None, is_userbot=False, is_group_context=False): 
    DC_LOCATIONS = SmartDCLocate() 
    premium_status = "Yes" if user.is_premium else "No" 
    dc_location = DC_LOCATIONS.get(user.dc_id, "Unknown") 
    account_created = estimate_account_creation_date(user.id) 
    account_created_str = account_created.strftime("%B %d, %Y") 
    account_age = calculate_account_age(account_created) 
     
    full_name = f"{user.first_name} {user.last_name or ''}".strip() 
     
    profile_type = "SmartUserBot's Profile Info" if is_userbot else ("Bot's Profile Info" if user.is_bot else "User's Profile Info") 
     
    response = ( 
        f"<b>🔍 Showing {profile_type} 📋</b>\n" 
        "<b>━━━━━━━━━━━━━━━━</b>\n" 
        f"<b>Full Name:</b> <b>{full_name}</b>\n" 
    ) 
     
    if user.username: 
        response += f"<b>Username:</b> @{user.username}\n" 
     
    response += f"<b>User ID:</b> <code>{user.id}</code>\n" 
     
    if is_group_context and chat: 
        response += f"<b>Chat ID:</b> <code>{chat.id}</code>\n" 
     
    if not user.is_bot: 
        response += f"<b>Premium User:</b> <b>{premium_status}</b>\n" 
     
    response += f"<b>Data Center:</b> <b>{dc_location}</b>\n" 
     
    if not user.is_bot: 
        response += ( 
            f"<b>Created On:</b> <b>{account_created_str}</b>\n" 
            f"<b>Account Age:</b> <b>{account_age}</b>\n" 
        ) 
     
    if hasattr(user, 'usernames') and user.usernames: 
        fragment_usernames = ", ".join([f"@{username.username}" for username in user.usernames]) 
        response += f"<b>Fragment Usernames:</b> {fragment_usernames}\n" 
     
    if hasattr(user, 'is_restricted') and user.is_restricted: 
        response += f"<b>Account Frozen:</b> <b>Yes</b>\n" 
    else: 
        response += f"<b>Account Frozen:</b> <b>No</b>\n" 
     
    if not user.is_bot and hasattr(user, 'status'): 
        status_display = get_status_display(user.status) 
        response += f"<b>Users Last Seen:</b> <b>{status_display}</b>\n" 
     
    if hasattr(user, 'is_support') and user.is_support: 
        response += f"<b>Telegram Staff:</b> <b>Yes</b>\n" 
     
    response += ( 
        f"<b>Permanent Link:</b> <a href='tg://user?id={user.id}'>Click Here</a>\n" 
        "<b>━━━━━━━━━━━━━━━━</b>\n" 
        "<b>👁 Thank You for Using Our Tool ✅</b>" 
    ) 
     
    return response 
 
def format_chat_response(chat): 
    DC_LOCATIONS = SmartDCLocate() 
    dc_location = DC_LOCATIONS.get(chat.dc_id, "Unknown") 
    
    chat_type_mapping = {
        ChatType.CHANNEL: "Channel",
        ChatType.GROUP: "Group", 
        ChatType.SUPERGROUP: "Supergroup",
        ChatType.PRIVATE: "Private Chat"
    }
    
    chat_type = chat_type_mapping.get(chat.type, "Unknown")
    full_name = chat.title 
     
    response = ( 
        f"<b>🔍 Showing {chat_type}'s Profile Info 📋</b>\n" 
        "<b>━━━━━━━━━━━━━━━━</b>\n" 
        f"<b>Full Name:</b> <b>{full_name}</b>\n" 
    ) 
     
    if chat.username: 
        response += f"<b>Username:</b> @{chat.username}\n" 
     
    response += ( 
        f"<b>Chat ID:</b> <code>{chat.id}</code>\n" 
        f"<b>Total Members:</b> <b>{chat.members_count if chat.members_count else 'Unknown'}</b>\n" 
    ) 
     
    if hasattr(chat, 'usernames') and chat.usernames: 
        fragment_usernames = ", ".join([f"@{username.username}" for username in chat.usernames]) 
        response += f"<b>Fragment Usernames:</b> {fragment_usernames}\n" 
     
    response += ( 
        f"<b>Permanent Link:</b> <a href='tg://resolve?domain={chat.username}'>Click Here</a>\n" if chat.username else "" 
    ) 
     
    response += ( 
        "<b>━━━━━━━━━━━━━━━━</b>\n" 
        "<b>👁 Thank You for Using Our Tool ✅</b>" 
    ) 
     
    return response 
 
async def get_profile_photo_file_id(client, entity):
    try:
        photo_iter = client.get_chat_photos(entity.id, limit=1)
        async for photo in photo_iter:
            if hasattr(photo, 'video_sizes') and photo.video_sizes:
                return photo.file_id, True
            else:
                return photo.file_id, False
    except Exception as e:
        logger.error(f"Error getting chat photos: {str(e)}")
        
    try:
        if hasattr(entity, 'photo') and entity.photo and hasattr(entity.photo, 'file_id'):
            return entity.photo.file_id, False
    except Exception as fallback_error:
        logger.error(f"Fallback direct photo access failed: {str(fallback_error)}")
        
    return None, False 
 
async def send_info_with_photo(message, response, entity, buttons=None): 
    photo_file_id, is_animated = await get_profile_photo_file_id(SmartPyro, entity) 
     
    try: 
        if photo_file_id: 
            try:
                if is_animated: 
                    await SmartAIO.send_animation( 
                        chat_id=message.chat.id, 
                        animation=photo_file_id, 
                        caption=response, 
                        parse_mode=ParseMode.HTML, 
                        reply_markup=buttons.build_menu(b_cols=1) if buttons else None 
                    ) 
                else: 
                    await SmartAIO.send_photo( 
                        chat_id=message.chat.id, 
                        photo=photo_file_id, 
                        caption=response, 
                        parse_mode=ParseMode.HTML, 
                        reply_markup=buttons.build_menu(b_cols=1) if buttons else None 
                    ) 
                logger.info("Info sent successfully with profile photo")
            except Exception as photo_send_error:
                logger.error(f"Error sending with photo file_id: {str(photo_send_error)}")
                await SmartAIO.send_message( 
                    chat_id=message.chat.id, 
                    text=response, 
                    parse_mode=ParseMode.HTML, 
                    reply_markup=buttons.build_menu(b_cols=1) if buttons else None 
                )
                logger.info("Info sent as fallback message due to photo sending error")
        else: 
            await SmartAIO.send_message( 
                chat_id=message.chat.id, 
                text=response, 
                parse_mode=ParseMode.HTML, 
                reply_markup=buttons.build_menu(b_cols=1) if buttons else None 
            )
            logger.info("Info sent without profile photo (no photo available)")
    except Exception as e: 
        logger.error(f"Error in send_info_with_photo: {str(e)}") 
        await SmartAIO.send_message( 
            chat_id=message.chat.id, 
            text=response, 
            parse_mode=ParseMode.HTML, 
            reply_markup=buttons.build_menu(b_cols=1) if buttons else None 
        )
        logger.info("Info sent as final fallback message") 
 
@dp.message(Command(commands=["info", "id"], prefix=BotCommands)) 
@new_task 
@SmartDefender 
async def handle_info_command(message: Message, bot: Bot): 
    if message.chat.type not in ["private", "group", "supergroup"]: 
        await send_message( 
            chat_id=message.chat.id, 
            text="<b>❌ This command only works in private or group chats</b>", 
            parse_mode=ParseMode.HTML 
        ) 
        return 
 
    logger.info("Received /info or /id command") 
    progress_message = await send_message( 
        chat_id=message.chat.id, 
        text="<code>Processing User Info...</code>", 
        parse_mode=ParseMode.HTML 
    ) 
 
    try: 
        command_parts = message.text.split() 
        is_group_context = message.chat.type in ["group", "supergroup"] 
         
        if len(command_parts) == 2 and command_parts[1].lower() == 'me': 
            logger.info("Fetching SmartUserBot info") 
            user = await SmartUserBot.get_me() 
            chat = await SmartPyro.get_chat(message.chat.id) if is_group_context else None 
            response = format_user_response(user, chat, is_userbot=True, is_group_context=is_group_context) 
            full_name = f"{user.first_name} {user.last_name or ''}".strip() 
             
            buttons = SmartButtons() 
            buttons.button(text=full_name, copy_text=str(user.id)) 
             
            await delete_messages(message.chat.id, [progress_message.message_id]) 
            await send_info_with_photo(message, response, user, buttons) 
            logger.info("UserBot info fetched successfully") 
             
        elif not command_parts or (len(command_parts) == 1 and not message.reply_to_message): 
            logger.info("Fetching current user info") 
            user = await SmartPyro.get_users(message.from_user.id) 
            chat = await SmartPyro.get_chat(message.chat.id) if is_group_context else None 
            response = format_user_response(user, chat, is_group_context=is_group_context) 
            full_name = f"{user.first_name} {user.last_name or ''}".strip() 
             
            buttons = SmartButtons() 
            buttons.button(text=full_name, copy_text=str(user.id)) 
             
            await delete_messages(message.chat.id, [progress_message.message_id]) 
            await send_info_with_photo(message, response, user, buttons) 
            logger.info("User info fetched successfully with buttons") 
 
        elif message.reply_to_message: 
            logger.info("Fetching info of the replied user or bot") 
            user = await SmartPyro.get_users(message.reply_to_message.from_user.id) 
            chat = await SmartPyro.get_chat(message.chat.id) if is_group_context else None 
            response = format_user_response(user, chat, is_group_context=is_group_context) 
            full_name = f"{user.first_name} {user.last_name or ''}".strip() 
             
            buttons = SmartButtons() 
            buttons.button(text=full_name, copy_text=str(user.id)) 
             
            await delete_messages(message.chat.id, [progress_message.message_id]) 
            await send_info_with_photo(message, response, user, buttons) 
            logger.info("Replied user info fetched successfully") 
 
        elif len(command_parts) > 1 and command_parts[1].lower() != 'me': 
            logger.info("Extracting username from the command") 
            username = command_parts[1].strip('@').replace('https://', '').replace('http://', '').replace('t.me/', '').replace('/', '').replace(':', '') 
 
            try: 
                logger.info(f"Fetching info for user or bot: {username}") 
                user = await SmartPyro.get_users(username) 
                chat = await SmartPyro.get_chat(message.chat.id) if is_group_context else None 
                response = format_user_response(user, chat, is_group_context=is_group_context) 
                full_name = f"{user.first_name} {user.last_name or ''}".strip() 
                 
                buttons = SmartButtons() 
                buttons.button(text=full_name, copy_text=str(user.id)) 
                 
                await delete_messages(message.chat.id, [progress_message.message_id]) 
                await send_info_with_photo(message, response, user, buttons) 
                logger.info("User/bot info fetched successfully with buttons") 
                 
            except (PeerIdInvalid, UsernameNotOccupied, IndexError): 
                logger.info(f"Username '{username}' not found as a user/bot. Checking for chat...") 
                try: 
                    chat = await SmartPyro.get_chat(username) 
                    response = format_chat_response(chat) 
                     
                    buttons = SmartButtons() 
                    buttons.button(text=chat.title, copy_text=str(chat.id)) 
                     
                    await delete_messages(message.chat.id, [progress_message.message_id]) 
                    await send_info_with_photo(message, response, chat, buttons) 
                    logger.info("Chat info fetched successfully with buttons") 
                     
                except (ChannelInvalid, PeerIdInvalid): 
                    chat_type = "Channel" if "channel" in username.lower() else "Group" 
                    error_message = ( 
                        "<b>Looks Like I Don't Have Control Over The Channel</b>" 
                        if chat_type == "Channel" 
                        else "<b>Looks Like I Don't Have Control Over The Group</b>" 
                    ) 
                    await SmartAIO.edit_message_text( 
                        chat_id=message.chat.id, 
                        message_id=progress_message.message_id, 
                        text=error_message, 
                        parse_mode=ParseMode.HTML 
                    ) 
                    logger.error(f"Permission error: {error_message}") 
                     
                except Exception as e: 
                    logger.error(f"Error fetching chat info: {str(e)}") 
                    await SmartAIO.edit_message_text( 
                        chat_id=message.chat.id, 
                        message_id=progress_message.message_id, 
                        text="<b>Looks Like I Don't Have Control Over The Group</b>", 
                        parse_mode=ParseMode.HTML 
                    ) 
                     
            except Exception as e: 
                logger.error(f"Error fetching user or bot info: {str(e)}") 
                await SmartAIO.edit_message_text( 
                    chat_id=message.chat.id, 
                    message_id=progress_message.message_id, 
                    text="<b>Looks Like I Don't Have Control Over The User</b>", 
                    parse_mode=ParseMode.HTML 
                ) 
                 
    except Exception as e: 
        logger.error(f"Unhandled exception: {str(e)}") 
        await Smart_Notify(bot, "info", e, message) 
        await SmartAIO.edit_message_text( 
            chat_id=message.chat.id, 
            message_id=progress_message.message_id, 
            text="<b>Looks Like I Don't Have Control Over The User</b>", 
            parse_mode=ParseMode.HTML 
        )