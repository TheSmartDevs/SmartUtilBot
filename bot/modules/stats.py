import asyncio
from datetime import datetime, timedelta
from aiogram import Bot
from aiogram.enums import ChatType
from aiogram.filters import Command, ChatMemberUpdatedFilter
from aiogram.types import Message, ChatMemberUpdated
from pyrogram import Client
from pyrogram.enums import ParseMode as SmartParseMode, ChatType as PyrogramChatType
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated, ChatWriteForbidden, PeerIdInvalid
from pyrogram.types import InlineKeyboardMarkup as PyrogramInlineKeyboardMarkup, InlineKeyboardButton as PyrogramInlineKeyboardButton
from bot import dp, SmartPyro
from bot.helpers.botutils import send_message, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.buttons import SmartButtons
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.guard import admin_only
from bot.core.mongo import SmartUsers
from bot.modules.string import session_data
from config import UPDATE_CHANNEL_URL
import re

async def update_user_activity(user_id: int, chat_id: int = None, is_group: bool = False):
    try:
        now = datetime.utcnow()
        user_update_data = {
            "$set": {
                "user_id": user_id,
                "last_activity": now,
                "is_group": False
            },
            "$inc": {"activity_count": 1}
        }
        await SmartUsers.update_one(
            {"user_id": user_id, "is_group": False},
            user_update_data,
            upsert=True
        )
        LOGGER.debug(f"Updated user activity for user_id {user_id}")
        if is_group and chat_id and chat_id != user_id:
            group_update_data = {
                "$set": {
                    "user_id": chat_id,
                    "last_activity": now,
                    "is_group": True
                },
                "$inc": {"activity_count": 1}
            }
            await SmartUsers.update_one(
                {"user_id": chat_id, "is_group": True},
                group_update_data,
                upsert=True
            )
            LOGGER.debug(f"Updated group activity for chat_id {chat_id}")
    except Exception as e:
        LOGGER.error(f"Error updating user activity for user_id {user_id}, chat_id {chat_id}: {str(e)}")

@dp.message(Command(commands=["broadcast", "send"], prefix=BotCommands))
@admin_only
async def broadcast_handler(message: Message, bot: Bot):
    if not message.reply_to_message:
        await send_message(
            chat_id=message.chat.id,
            text="<b>Please reply to a message to broadcast/send it.</b>",
            parse_mode=SmartParseMode.HTML
        )
        return
    if not (message.reply_to_message.text or message.reply_to_message.photo or
            message.reply_to_message.video or message.reply_to_message.audio or
            message.reply_to_message.document):
        await send_message(
            chat_id=message.chat.id,
            text="<b>Please reply to a valid message (text, photo, video, audio, or document).</b>",
            parse_mode=SmartParseMode.HTML
        )
        return
    command = get_args(message)[0].lower() if get_args(message) else message.text.lstrip(''.join(BotCommands)).split()[0].lower()
    is_broadcast = command == "broadcast"
    LOGGER.info(f"{'Broadcast' if is_broadcast else 'Send'} initiated by user_id {message.from_user.id}")
    try:
        await process_broadcast(SmartPyro, message.reply_to_message, is_broadcast, message.chat.id, bot)
    except Exception as e:
        await Smart_Notify(bot, "broadcast_handler", e, message)
        await send_message(
            chat_id=message.chat.id,
            text="<b>Sorry Broadcast Send Failed ❌</b>",
            parse_mode=SmartParseMode.HTML
        )

async def process_broadcast(client: Client, content: Message, is_broadcast: bool, chat_id: int, bot: Bot):
    try:
        LOGGER.info(f"Processing {'broadcast' if is_broadcast else 'forward'}")
        processing_msg = await send_message(
            chat_id=chat_id,
            text="<b>Broadcasting Your Message To Users...</b>",
            parse_mode=SmartParseMode.HTML
        )
        bot_info = await client.get_me()
        bot_id = bot_info.id
        chats = await SmartUsers.find({}, {"user_id": 1, "is_group": 1}).to_list(None)
        user_ids = [chat["user_id"] for chat in chats if not chat.get("is_group", False) and chat["user_id"] != bot_id]
        group_ids = [chat["user_id"] for chat in chats if chat.get("is_group", False) and chat["user_id"] != bot_id]
        LOGGER.info(f"Found {len(user_ids)} users and {len(group_ids)} groups to broadcast to")
        successful_users, blocked_users, successful_groups, failed_groups = 0, 0, 0, 0
        start_time = datetime.now()
        buttons = SmartButtons()
        buttons.button(text="Updates Channel", url=UPDATE_CHANNEL_URL)
        aiogram_keyboard = buttons.build_menu(b_cols=1)
        pyrogram_buttons = [[PyrogramInlineKeyboardButton(text=btn.text, url=btn.url)] for row in aiogram_keyboard.inline_keyboard for btn in row if btn.url]
        keyboard = PyrogramInlineKeyboardMarkup(pyrogram_buttons) if pyrogram_buttons else None
        all_chat_ids = user_ids + group_ids
        LOGGER.debug(f"Starting broadcast to {len(all_chat_ids)} chats")
        async def send_to_chat(target_chat_id: int):
            try:
                if content.text:
                    sent_msg = await client.send_message(
                        target_chat_id,
                        content.text,
                        parse_mode=SmartParseMode.HTML,
                        reply_markup=keyboard
                    )
                    if target_chat_id in group_ids:
                        chat = await client.get_chat(target_chat_id)
                        if chat.type in [PyrogramChatType.GROUP, PyrogramChatType.SUPERGROUP]:
                            await client.pin_chat_message(target_chat_id, sent_msg.id)
                elif is_broadcast:
                    if not (content.text or content.photo or content.video or content.audio or content.document):
                        raise ValueError("Unsupported message type")
                    sent_msg = await client.copy_message(
                        target_chat_id,
                        content.chat.id,
                        content.message_id,
                        reply_markup=keyboard
                    )
                    if target_chat_id in group_ids:
                        chat = await client.get_chat(target_chat_id)
                        if chat.type in [PyrogramChatType.GROUP, PyrogramChatType.SUPERGROUP]:
                            await client.pin_chat_message(target_chat_id, sent_msg.id)
                else:
                    await client.forward_messages(
                        target_chat_id,
                        content.chat.id,
                        content.message_id
                    )
                return ("user" if target_chat_id in user_ids else "group", "success")
            except FloodWait as e:
                LOGGER.warning(f"FloodWait for chat_id {target_chat_id}: Waiting {e.value}s")
                await asyncio.sleep(e.value)
                return await send_to_chat(target_chat_id)
            except UserIsBlocked:
                LOGGER.error(f"Bot blocked by user: chat_id {target_chat_id}")
                return ("user" if target_chat_id in user_ids else "group", "blocked")
            except (InputUserDeactivated, ChatWriteForbidden, PeerIdInvalid):
                LOGGER.error(f"Failed to send to chat_id {target_chat_id}: Chat not found or forbidden")
                return ("user" if target_chat_id in user_ids else "group", "blocked" if target_chat_id in user_ids else "failed")
            except Exception as e:
                LOGGER.error(f"Error sending to chat_id {target_chat_id}: {str(e)}")
                return ("user" if target_chat_id in user_ids else "group", "blocked" if target_chat_id in user_ids else "failed")
        batch_size = 50
        for i in range(0, len(all_chat_ids), batch_size):
            batch_ids = all_chat_ids[i:i + batch_size]
            results = await asyncio.gather(*[send_to_chat(chat_id) for chat_id in batch_ids], return_exceptions=True)
            for result in results:
                if isinstance(result, tuple):
                    chat_type, status = result
                    if chat_type == "user":
                        if status == "success":
                            successful_users += 1
                        elif status == "blocked":
                            blocked_users += 1
                    elif chat_type == "group":
                        if status == "success":
                            successful_groups += 1
                        elif status == "failed":
                            failed_groups += 1
        time_diff = (datetime.now() - start_time).seconds
        await processing_msg.delete()
        total_chats = successful_users + successful_groups
        buttons = SmartButtons()
        buttons.button(text="Updates Channel", url=UPDATE_CHANNEL_URL)
        keyboard = buttons.build_menu(b_cols=1)
        summary_msg = await send_message(
            chat_id=chat_id,
            text=(
                f"<b>Smart Broadcast Successful ✅</b>\n"
                f"<b>━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>⊗ To Users: {successful_users} Users</b>\n"
                f"<b>⊗ Blocked Users: {blocked_users} Users</b>\n"
                f"<b>⊗ To Groups: {successful_groups} Groups</b>\n"
                f"<b>⊗ Failed Groups: {failed_groups} Groups</b>\n"
                f"<b>⊗ Total Chats: {total_chats} Chats</b>\n"
                f"<b>━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>Smooth Telecast → Activated ✅</b>"
            ),
            parse_mode=SmartParseMode.HTML,
            reply_markup=keyboard
        )
        chat = await bot.get_chat(chat_id)
        if chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
            await bot.pin_chat_message(chat_id, summary_msg.message_id)
        LOGGER.info(f"{'Broadcast' if is_broadcast else 'Forward'} completed: {successful_users} users, {successful_groups} groups, "
                    f"{blocked_users} blocked users, {failed_groups} failed groups")
    except Exception as e:
        await Smart_Notify(bot, "process_broadcast", e)
        LOGGER.error(f"Error in {'broadcast' if is_broadcast else 'forward'}: {str(e)}")
        await send_message(chat_id, "<b>Sorry Broadcast Send Failed ❌</b>", parse_mode=SmartParseMode.HTML)

@dp.message(Command(commands=["stats", "report", "status"], prefix=BotCommands))
@admin_only
async def stats_handler(message: Message, bot: Bot):
    try:
        now = datetime.utcnow()
        daily_users = await SmartUsers.count_documents({"is_group": False, "last_activity": {"$gte": now - timedelta(days=1)}})
        weekly_users = await SmartUsers.count_documents({"is_group": False, "last_activity": {"$gte": now - timedelta(weeks=1)}})
        monthly_users = await SmartUsers.count_documents({"is_group": False, "last_activity": {"$gte": now - timedelta(days=30)}})
        yearly_users = await SmartUsers.count_documents({"is_group": False, "last_activity": {"$gte": now - timedelta(days=365)}})
        total_users = await SmartUsers.count_documents({"is_group": False})
        total_groups = await SmartUsers.count_documents({"is_group": True})
        buttons = SmartButtons()
        buttons.button(text="Updates Channel", url=UPDATE_CHANNEL_URL)
        keyboard = buttons.build_menu(b_cols=1)
        await send_message(
            chat_id=message.chat.id,
            text=(
                f"<b>Smart Bot Status ⇾ Report ✅</b>\n"
                f"<b>━━━━━━━━━━━━━━━━</b>\n"
                f"<b>Users & Groups Engagements:</b>\n"
                f"<b>1 Day:</b> {daily_users} users were active\n"
                f"<b>1 Week:</b> {weekly_users} users were active\n"
                f"<b>1 Month:</b> {monthly_users} users were active\n"
                f"<b>1 Year:</b> {yearly_users} users were active\n"
                f"<b>Total Connected Groups:</b> {total_groups}\n"
                f"<b>━━━━━━━━━━━━━━━━</b>\n"
                f"<b>Total Smart Tools Users:</b> {total_users} ✅"
            ),
            parse_mode=SmartParseMode.HTML,
            reply_markup=keyboard
        )
        LOGGER.info("Stats command completed")
    except Exception as e:
        await Smart_Notify(bot, "stats_handler", e, message)
        LOGGER.error(f"Error in stats: {str(e)}")
        await send_message(
            chat_id=message.chat.id,
            text="<b>Sorry Database Client Unavailable ❌</b>",
            parse_mode=SmartParseMode.HTML
        )

async def group_added_handler(message: Message, bot: Bot):
    try:
        bot_info = await bot.get_me()
        for member in message.new_chat_members:
            if member.id == bot_info.id:
                chat_id = message.chat.id
                await update_user_activity(member.id, chat_id, is_group=True)
                await send_message(
                    chat_id=chat_id,
                    text="<b>Thank you for adding me to this group!</b>",
                    parse_mode=SmartParseMode.HTML,
                    reply_to_message_id=message.message_id
                )
                LOGGER.info(f"Bot added to group {chat_id}")
    except Exception as e:
        await Smart_Notify(bot, "group_added_handler", e, message)
        LOGGER.error(f"Error in group_added_handler for chat_id {message.chat.id}: {str(e)}")

@dp.chat_member(ChatMemberUpdatedFilter(member_status_changed=["member", "administrator", "kicked", "left"]))
async def group_removed_handler(update: ChatMemberUpdated, bot: Bot):
    try:
        bot_info = await bot.get_me()
        if update.new_chat_member.user.id == bot_info.id and update.new_chat_member.status in ["kicked", "left"]:
            chat_id = update.chat.id
            await SmartUsers.delete_one({"user_id": chat_id, "is_group": True})
            LOGGER.info(f"Bot removed/banned from group {chat_id}, removed from database")
    except Exception as e:
        await Smart_Notify(bot, "group_removed_handler", e)
        LOGGER.error(f"Error in group_removed_handler for chat_id {update.chat.id}: {str(e)}")

@dp.message(lambda message: message.chat.type in [ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP] and not message.from_user.is_bot and message.text and not message.text.startswith(tuple(BotCommands)) and message.chat.id not in session_data)
async def update_user_activity_handler(message: Message, bot: Bot):
    try:
        user_id = message.from_user.id
        chat_id = message.chat.id
        is_group = message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]
        await update_user_activity(user_id, chat_id, is_group)
        LOGGER.debug(f"Activity updated for user {user_id} in chat {chat_id} (is_group: {is_group})")
    except Exception as e:
        await Smart_Notify(bot, "update_user_activity_handler", e, message)
        LOGGER.error(f"Error in update_user_activity_handler for message_id {getattr(message, 'message_id', 'unknown')}: {str(e)}")