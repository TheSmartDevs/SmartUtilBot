# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
import traceback
from datetime import datetime
from typing import Optional, Union
from aiogram import Bot
from aiogram.types import Message
from aiogram.enums import ParseMode, ChatMemberStatus
from bot import dp
from bot.helpers.botutils import send_message
from bot.helpers.buttons import SmartButtons
from bot.helpers.logger import LOGGER
from config import OWNER_ID, DEVELOPER_USER_ID, LOG_CHANNEL_ID, UPDATE_CHANNEL_URL

TRACEBACK_DATA = {}

async def check_channel_membership(bot: Bot, user_id: int) -> tuple[bool, str, Optional[int]]:
    try:
        if not LOG_CHANNEL_ID:
            return False, "LOG_CHANNEL_ID is not configured", None

        channel_id = LOG_CHANNEL_ID

        if isinstance(channel_id, str):
            if not channel_id.startswith('@'):
                try:
                    channel_id = int(channel_id)
                except (ValueError, TypeError):
                    return False, f"Invalid LOG_CHANNEL_ID format: {LOG_CHANNEL_ID}. Must be a valid integer or username.", None

        if isinstance(channel_id, int):
            if channel_id > 0:
                channel_id = -channel_id
            if not str(abs(channel_id)).startswith('100'):
                channel_id = int(f"-100{abs(channel_id)}")

        result = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        
        valid_statuses = [
            ChatMemberStatus.MEMBER, 
            ChatMemberStatus.ADMINISTRATOR, 
            ChatMemberStatus.CREATOR
        ]
        
        if hasattr(result, 'status') and result.status in valid_statuses:
            return True, "", channel_id
        elif str(type(result).__name__) in ["ChatMemberOwner", "ChatMemberAdministrator", "ChatMemberMember"]:
            return True, "", channel_id
        else:
            return False, f"User {user_id} is not a member of the channel", channel_id

    except Exception as e:
        error_msg = str(e).lower()
        if "user not found" in error_msg:
            return False, f"User {user_id} not found in channel", None
        elif "chat not found" in error_msg or "chat_invalid" in error_msg:
            return False, f"Channel {LOG_CHANNEL_ID} not found or invalid", None
        elif "peer_id_invalid" in error_msg:
            return False, f"Invalid channel ID: {LOG_CHANNEL_ID}", None
        elif "forbidden" in error_msg:
            return False, f"Bot doesn't have permission to check membership in channel {LOG_CHANNEL_ID}", None
        else:
            return False, f"Failed to check membership: {str(e)}", None

async def Smart_Notify(bot: Bot, command: str, error: Union[Exception, str], message: Optional[Message] = None) -> None:
    try:
        bot_info = await bot.get_me()
        is_member, error_msg, channel_id = await check_channel_membership(bot, bot_info.id)
        if not is_member:
            LOGGER.error(error_msg)

        user_info = {'id': "N/A", 'mention': "Unknown User", 'username': "N/A", 'full_name': "N/A"}
        chat_id_user = "N/A"
        if message and message.from_user:
            user = message.from_user
            full_name = f"{user.first_name} {user.last_name or ''}".strip()
            user_info = {
                'id': user.id,
                'mention': f"<a href='tg://user?id={user.id}'>{full_name}</a>",
                'username': f"@{user.username}" if user.username else "N/A",
                'full_name': full_name
            }
            chat_id_user = getattr(message.chat, 'id', "N/A")

        if isinstance(error, str):
            error_type = "StringError"
            error_message = error
            traceback_text = "N/A"
            error_level = "WARNING"
        else:
            error_type = type(error).__name__
            error_message = str(error)
            traceback_text = "".join(traceback.format_exception(type(error), error, error.__traceback__)) if error.__traceback__ else "N/A"
            error_level = "WARNING" if isinstance(error, (ValueError, UserWarning)) else "ERROR" if isinstance(error, RuntimeError) else "CRITICAL"

        now = datetime.now()
        full_timestamp = now.strftime('%d-%m-%Y %H:%M:%S %p')
        formatted_date = now.strftime('%d-%m-%Y')
        formatted_time = now.strftime('%H:%M:%S')
        error_id = f"{int(now.timestamp() * 1000000)}"
        TRACEBACK_DATA[error_id] = {
            'error_type': error_type,
            'error_level': error_level,
            'traceback_text': traceback_text,
            'full_timestamp': full_timestamp,
            'command': command,
            'error_message': error_message,
            'user_info': user_info,
            'chat_id': chat_id_user,
            'formatted_date': formatted_date,
            'formatted_time': formatted_time
        }

        error_report = (
            "<b>🚨 Smart Util ⚙️ New Bug Report</b>\n"
            "<b>━━━━━━━━━━━━━━━━</b>\n"
            f"<b>🧩 Command:</b> {command}\n"
            f"<b>👤 User:</b> {user_info['mention']}\n"
            f"<b>⚡️ User ID:</b> <code>{user_info['id']}</code>\n"
            f"<b>📍 Chat:</b> {chat_id_user}\n"
            f"<b>📅 Time:</b> {formatted_time}\n"
            f"<b>❗️ Error:</b> {error_type}\n"
            f"<b>📝 Message:</b> {error_message}\n"
            "<b>━━━━━━━━━━━━━━━━</b>\n"
            "<b>📂 Traceback:</b> Tap below to inspect"
        )

        buttons = SmartButtons()
        if user_info['id'] != "N/A":
            buttons.button(text="👤 View Profile", url=f"tg://user?id={user_info['id']}", position="header")
            buttons.button(text="🛠 Dev", url=f"tg://user?id={DEVELOPER_USER_ID}", position="header")
        buttons.button(text="📄 View Traceback", callback_data=f"viewtrcbc{error_id}$", position="footer")
        reply_markup = buttons.build_menu(b_cols=1, h_cols=2, f_cols=1)

        await send_message(
            chat_id=OWNER_ID,
            text=error_report,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
            disable_web_page_preview=True,
            disable_notification=(error_level == "WARNING")
        )

        if is_member and channel_id:
            minimal_report = (
                "<b>🚨 Smart Util ⚙️ New Bug Report</b>\n"
                "<b>━━━━━━━━━━━━━━━━</b>\n"
                f"<b>🧩 Command:</b> {command}\n"
                f"<b>👤 User:</b> {user_info['mention']}\n"
                f"<b>⚡️ User ID:</b> <code>{user_info['id']}</code>\n"
                f"<b>📍 Chat:</b> {chat_id_user}\n"
                f"<b>📅 Time:</b> {formatted_time}\n"
                f"<b>❗️ Error:</b> {error_type}\n"
                f"<b>📝 Message:</b> {error_message}\n"
                "<b>━━━━━━━━━━━━━━━━</b>\n"
                "<b>📂 Traceback:</b> Tap below to inspect"
            )
            channel_buttons = SmartButtons()
            channel_buttons.button(text="Updates Channel", url=UPDATE_CHANNEL_URL)
            channel_reply_markup = channel_buttons.build_menu(b_cols=1)
            await send_message(
                chat_id=channel_id,
                text=minimal_report,
                parse_mode=ParseMode.HTML,
                reply_markup=channel_reply_markup,
                disable_web_page_preview=True,
                disable_notification=(error_level == "WARNING")
            )

        LOGGER.info(f"Admin notification sent for command: {command} with error_id: {error_id}")

    except Exception as e:
        LOGGER.error(f"Failed to send admin notification: {e}")
        LOGGER.error(traceback.format_exc())

@dp.callback_query(lambda c: c.data.startswith("viewtrcbc"))
async def handle_traceback_callback(callback_query):
    try:
        LOGGER.info(f"Traceback callback triggered: {callback_query.data}")
        error_id = callback_query.data.replace("viewtrcbc", "").replace("$", "")
        LOGGER.info(f"Extracted error_id: {error_id}")
        if error_id not in TRACEBACK_DATA:
            LOGGER.warning(f"Traceback data not found for error_id: {error_id}")
            LOGGER.info(f"Available error_ids: {list(TRACEBACK_DATA.keys())}")
            await callback_query.answer("❌ Traceback data not found or expired!", show_alert=True)
            return

        data = TRACEBACK_DATA[error_id]
        traceback_text = data['traceback_text']
        if len(traceback_text) > 2000:
            traceback_text = traceback_text[:2000] + "\n... (truncated)"
        traceback_escaped = traceback_text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        issue_escaped = data['error_message'][:200].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

        traceback_message = (
            "<b>📄 Full Traceback — Smart Util ⚙️</b>\n"
            "<b>━━━━━━━━━━━━━━━━</b>\n"
            f"<b>🧩 Command:</b> {data['command']}\n"
            f"<b>⚠️ Error Type:</b> {data['error_type']}\n"
            f"<b>🧠 Summary:</b> {issue_escaped}\n"
            f"<b>📂 Traceback Dump:</b>\n"
            f"<blockquote expandable=True>{traceback_escaped}</blockquote>\n"
            "<b>━━━━━━━━━━━━━━━━</b>\n"
            "<b>🔙 Return:</b> Tap below to go back"
        )

        back_button = SmartButtons()
        back_button.button(text="🔙 Back To Main", callback_data=f"backtosummary{error_id}$")
        back_reply_markup = back_button.build_menu(b_cols=1)

        await callback_query.message.edit_text(
            text=traceback_message,
            parse_mode=ParseMode.HTML,
            reply_markup=back_reply_markup,
            disable_web_page_preview=True
        )
        await callback_query.answer("Here Is The Full Traceback ✅")
        LOGGER.info(f"Traceback displayed successfully for error_id: {error_id}")

    except Exception as e:
        LOGGER.error(f"Error in traceback callback: {e}")
        LOGGER.error(traceback.format_exc())
        try:
            await callback_query.answer("Failed To Show Traceback ❌", show_alert=True)
        except:
            pass

@dp.callback_query(lambda c: c.data.startswith("backtosummary"))
async def handle_back_callback(callback_query):
    try:
        LOGGER.info(f"Back to summary callback triggered: {callback_query.data}")
        error_id = callback_query.data.replace("backtosummary", "").replace("$", "")
        if error_id not in TRACEBACK_DATA:
            await callback_query.answer("Failed To Show Traceback ❌", show_alert=True)
            return

        data = TRACEBACK_DATA[error_id]
        error_report = (
            "<b>🚨 Smart Util ⚙️ New Bug Report</b>\n"
            "<b>━━━━━━━━━━━━━━━━</b>\n"
            f"<b>🧩 Command:</b> {data['command']}\n"
            f"<b>👤 User:</b> {data['user_info']['mention']}\n"
            f"<b>⚡️ User ID:</b> <code>{data['user_info']['id']}</code>\n"
            f"<b>📍 Chat:</b> {data['chat_id']}\n"
            f"<b>📅 Time:</b> {data['formatted_time']}\n"
            f"<b>❗️ Error:</b> {data['error_type']}\n"
            f"<b>📝 Message:</b> {data['error_message']}\n"
            "<b>━━━━━━━━━━━━━━━━</b>\n"
            "<b>📂 Traceback:</b> Tap below to inspect"
        )

        buttons = SmartButtons()
        if data['user_info']['id'] != "N/A":
            buttons.button(text="👤 View Profile", url=f"tg://user?id={data['user_info']['id']}", position="header")
            buttons.button(text="🛠 Dev", url=f"tg://user?id={DEVELOPER_USER_ID}", position="header")
        buttons.button(text="📄 View Traceback", callback_data=f"viewtrcbc{error_id}$", position="footer")
        reply_markup = buttons.build_menu(b_cols=1, h_cols=2, f_cols=1)

        await callback_query.message.edit_text(
            text=error_report,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup,
            disable_web_page_preview=True
        )
        await callback_query.answer("Summary Loaded Successful ✅!")
        LOGGER.info(f"Back to summary successful for error_id: {error_id}")

    except Exception as e:
        LOGGER.error(f"Error in back callback: {e}")
        LOGGER.error(traceback.format_exc())
        try:
            await callback_query.answer("Error ❌ Loading Summary", show_alert=True)
        except:
            pass

def cleanup_old_traceback_data():
    try:
        current_time = datetime.now().timestamp() * 1000000
        keys_to_remove = []
        for key in TRACEBACK_DATA.keys():
            try:
                timestamp = float(key)
                if current_time - timestamp > 86400000000:
                    keys_to_remove.append(key)
            except:
                pass
        for key in keys_to_remove:
            del TRACEBACK_DATA[key]
        if keys_to_remove:
            LOGGER.info(f"Cleaned up {len(keys_to_remove)} old traceback entries")
    except Exception as e:
        LOGGER.error(f"Error in cleanup: {e}")

try:
    cleanup_old_traceback_data()
except:
    pass