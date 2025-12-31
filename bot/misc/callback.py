import os
import time
import subprocess
from datetime import datetime, timedelta
import psutil
from aiogram import Bot
from aiogram.types import CallbackQuery
from aiogram.enums import ParseMode
from bot.helpers.buttons import SmartButtons
from bot.helpers.botutils import send_message
from bot.helpers.genbtn import responses, main_menu_keyboard, second_menu_keyboard, third_menu_keyboard, fourth_menu_keyboard
from bot.helpers.donateutils import DONATION_OPTIONS_TEXT, get_donation_buttons, handle_donate_callback
from bot.helpers.logger import LOGGER
from bot.core.mongo import SmartUsers
from config import UPDATE_CHANNEL_URL
import html

async def handle_callback_query(callback_query: CallbackQuery, bot: Bot):
    call = callback_query
    chat_id = call.message.chat.id
    user_id = call.from_user.id

    if call.data == "stats":
        now = datetime.utcnow()
        daily_users = await SmartUsers.count_documents({"is_group": False, "last_activity": {"$gte": now - timedelta(days=1)}})
        weekly_users = await SmartUsers.count_documents({"is_group": False, "last_activity": {"$gte": now - timedelta(weeks=1)}})
        monthly_users = await SmartUsers.count_documents({"is_group": False, "last_activity": {"$gte": now - timedelta(days=30)}})
        yearly_users = await SmartUsers.count_documents({"is_group": False, "last_activity": {"$gte": now - timedelta(days=365)}})
        total_users = await SmartUsers.count_documents({"is_group": False})
        total_groups = await SmartUsers.count_documents({"is_group": True})
        stats_text = (
            f"<b>Smart Bot Status ⇾ Report ✅</b>\n"
            f"<b>━━━━━━━━━━━━━━━━</b>\n"
            f"<b>Users & Groups Engagements:</b>\n"
            f"<b>1 Day:</b> {daily_users} users were active\n"
            f"<b>1 Week:</b> {weekly_users} users were active\n"
            f"<b>1 Month:</b> {monthly_users} users were active\n"
            f"<b>1 Year:</b> {yearly_users} users were active\n"
            f"<b>Total Connected Groups:</b> {total_groups}\n"
            f"<b>━━━━━━━━━━━━━━━━</b>\n"
            f"<b>Total Smart Util Users:</b> {total_users} ✅"
        )
        back_button = SmartButtons()
        back_button.button(text="⬅️ Back", callback_data="fstats")
        back_button = back_button.build_menu(b_cols=1, h_cols=1, f_cols=1)
        await call.message.edit_text(stats_text, parse_mode=ParseMode.HTML, reply_markup=back_button, disable_web_page_preview=True)
        return

    if call.data == "fstats":
        stats_dashboard_text = (
            f"<b>🗒 Smart Util Basic Statistics Menu 🔍</b>\n"  
            f"<b>━━━━━━━━━━━━━━━━━</b>\n"  
            f"Stay Updated With Real Time Insights....⚡️\n\n"  
            f"⊗ <b>Full Statistics:</b> Get Full Statistics Of Smart Tool ⚙️\n"  
            f"⊗ <b>Top Users:</b> Get Top User's Leaderboard 🔥\n"  
            f"⊗ <b>Growth Trends:</b> Get Knowledge About Growth 👁\n"  
            f"⊗ <b>Activity Times:</b> See Which User Is Most Active ⏰\n"  
            f"⊗ <b>Milestones:</b> Track Special Achievements 🏅\n\n"  
            f"<b>━━━━━━━━━━━━━━━━━</b>\n"  
            f"<b>💡 Select an option and take control:</b>\n"
        )
        stats_dashboard_buttons = SmartButtons()
        stats_dashboard_buttons.button(text="📈 Usage Report", callback_data="stats")
        stats_dashboard_buttons.button(text="🏆 Top Users", callback_data="top_users_1")
        stats_dashboard_buttons.button(text="⬅️ Back", callback_data="about_me")
        stats_dashboard_buttons = stats_dashboard_buttons.build_menu(b_cols=2, h_cols=1, f_cols=1)
        await call.message.edit_text(stats_dashboard_text, parse_mode=ParseMode.HTML, reply_markup=stats_dashboard_buttons, disable_web_page_preview=True)
        return

    if call.data.startswith("top_users_"):
        page = int(call.data.split("_")[-1])
        users_per_page = 9
        now = datetime.utcnow()
        daily_users = await SmartUsers.find({"is_group": False, "last_activity": {"$gte": now - timedelta(days=1)}}).to_list(None)
        total_users = len(daily_users)
        total_pages = (total_users + users_per_page - 1) // users_per_page
        start_index = (page - 1) * users_per_page
        end_index = start_index + users_per_page
        paginated_users = daily_users[start_index:end_index]

        top_users_text = (
            f"<b>🏆 Top Users (All-time) — page {page}/{total_pages if total_pages > 0 else 1}:</b>\n"
            f"<b>━━━━━━━━━━━━━━━</b>\n"
        )
        for i, user in enumerate(paginated_users, start=start_index + 1):
            user_id = user['user_id']
            try:
                telegram_user = await bot.get_chat(user_id)
                full_name = f"{telegram_user.first_name} {telegram_user.last_name or ''}".strip()
                full_name_escaped = html.escape(full_name)
            except Exception as e:
                LOGGER.error(f"Failed to fetch user {user_id}: {e}")
                full_name_escaped = f"User_{user_id}"
            rank_emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🔸"
            top_users_text += f"<b>{rank_emoji} {i}.</b> <a href=\"tg://user?id={user_id}\">{full_name_escaped}</a>\n<b> - User Id :</b> <code>{user_id}</code>\n\n"

        top_users_buttons = SmartButtons()
        if page == 1 and total_pages > 1:
            top_users_buttons.button(text="Next ➡️", callback_data=f"top_users_{page+1}")
            top_users_buttons.button(text="⬅️ Back", callback_data="fstats")
        elif page > 1 and page < total_pages:
            top_users_buttons.button(text="⬅️ Previous", callback_data=f"top_users_{page-1}")
            top_users_buttons.button(text="Next ➡️", callback_data=f"top_users_{page+1}")
        elif page == total_pages and page > 1:
            top_users_buttons.button(text="⬅️ Previous", callback_data=f"top_users_{page-1}")
        else:
            top_users_buttons.button(text="⬅️ Back", callback_data="fstats")
        top_users_buttons = top_users_buttons.build_menu(b_cols=2 if page != total_pages else 1, h_cols=1, f_cols=1)
        await call.message.edit_text(top_users_text, parse_mode=ParseMode.HTML, reply_markup=top_users_buttons, disable_web_page_preview=True)
        return

    if call.data == "server":
        try:
            ping_output = subprocess.getoutput("ping -c 1 google.com")
            ping = ping_output.split("time=")[1].split()[0] if "time=" in ping_output else "N/A"
        except:
            ping = "N/A"

        disk = psutil.disk_usage('/')
        total_disk = disk.total / (2**30)
        used_disk = disk.used / (2**30)
        free_disk = disk.free / (2**30)
        mem = psutil.virtual_memory()
        total_mem = mem.total / (2**30)
        used_mem = mem.used / (2**30)
        available_mem = mem.available / (2**30)
        cpu_percent = psutil.cpu_percent(interval=1)

        server_status_text = (
            f"<b>⚙️ Server Status Report</b>\n"
            f"<b>━━━━━━━━━━━━━━━</b>\n"
            f"<b>🛜 Connectivity:</b>\n"
            f"<b>- Ping:</b> {ping}\n"
            f"<b>- Status:</b> Online\n"
            f"<b>- CPU Load:</b> {cpu_percent}%\n\n"
            f"<b>💾 Server Storage:</b>\n"
            f"<b>- Total:</b> {total_disk:.2f} GB\n"
            f"<b>- Used:</b> {used_disk:.2f} GB\n"
            f"<b>- Available:</b> {free_disk:.2f} GB\n\n"
            f"<b>🧠 Memory Usage:</b>\n"
            f"<b>- Total:</b> {total_mem:.2f} GB\n"
            f"<b>- Used:</b> {used_mem:.2f} GB\n"
            f"<b>- Available:</b> {available_mem:.2f} GB"
        )
        back_button = SmartButtons()
        back_button.button(text="⬅️ Back", callback_data="about_me")
        back_button = back_button.build_menu(b_cols=1, h_cols=1, f_cols=1)
        await call.message.edit_text(server_status_text, parse_mode=ParseMode.HTML, reply_markup=back_button, disable_web_page_preview=True)
        return

    if call.data in responses:
        back_button = SmartButtons()
        if call.data == "server":
            back_button.button(text="⬅️ Back", callback_data="about_me")
        elif call.data == "stats":
            back_button.button(text="⬅️ Back", callback_data="fstats")
        elif call.data == "about_me":
            back_button.button(text="📊 Statistics", callback_data="fstats")
            back_button.button(text="💾 Server", callback_data="server")
            back_button.button(text="⭐️ Donate", callback_data="donate")
            back_button.button(text="⬅️ Back", callback_data="start_message", position="footer")
        elif call.data in ["ai_tools", "credit_cards", "crypto", "converter", "coupons", "decoders", "downloaders", "domain_check", "education_utils", "rembg"]:
            back_button.button(text="⬅️ Back", callback_data="main_menu")
        elif call.data in ["file_to_link", "github", "info", "message_to_txt", "network_tools", "number_lookup", "pdf_tools", "qr_code", "url_shortner", "random_address"]:
            back_button.button(text="⬅️ Back", callback_data="second_menu")
        elif call.data in ["string_session", "stripe_keys", "sticker", "stylish_text", "time_date", "text_split", "translate", "tempmail", "text_ocr", "bot_users_export"]:
            back_button.button(text="⬅️ Back", callback_data="third_menu")
        elif call.data in ["web_capture", "weather", "yt_tools", "mail_tools"]:
            back_button.button(text="⬅️ Back", callback_data="fourth_menu")
        else:
            back_button.button(text="⬅️ Back", callback_data="main_menu")
        back_button = back_button.build_menu(b_cols=3 if call.data == "about_me" else 1, h_cols=1, f_cols=1)
        await call.message.edit_text(
            text=responses[call.data][0],
            parse_mode=responses[call.data][1]['parse_mode'],
            disable_web_page_preview=True,
            reply_markup=back_button
        )

    elif call.data.startswith("donate_") or call.data.startswith("increment_donate_") or call.data.startswith("decrement_donate_") or call.data == "donate":
        await handle_donate_callback(bot, call)

    elif call.data == "main_menu":
        await call.message.edit_text("<b>Here are the Smart-Util Options: 👇</b>", parse_mode=ParseMode.HTML, reply_markup=main_menu_keyboard, disable_web_page_preview=True)

    elif call.data == "second_menu":
        await call.message.edit_text("<b>Here are the Smart-Util Options: 👇</b>", parse_mode=ParseMode.HTML, reply_markup=second_menu_keyboard, disable_web_page_preview=True)

    elif call.data == "third_menu":
        await call.message.edit_text("<b>Here are the Smart-Util Options: 👇</b>", parse_mode=ParseMode.HTML, reply_markup=third_menu_keyboard, disable_web_page_preview=True)

    elif call.data == "fourth_menu":
        await call.message.edit_text("<b>Here are the Smart-Util Options: 👇</b>", parse_mode=ParseMode.HTML, reply_markup=fourth_menu_keyboard, disable_web_page_preview=True)

    elif call.data == "next_1":
        await call.message.edit_text("<b>Here are the Smart-Util Options: 👇</b>", parse_mode=ParseMode.HTML, reply_markup=second_menu_keyboard, disable_web_page_preview=True)

    elif call.data == "next_2":
        await call.message.edit_text("<b>Here are the Smart-Util Options: 👇</b>", parse_mode=ParseMode.HTML, reply_markup=third_menu_keyboard, disable_web_page_preview=True)

    elif call.data == "next_3":
        await call.message.edit_text("<b>Here are the Smart-Util Options: 👇</b>", parse_mode=ParseMode.HTML, reply_markup=fourth_menu_keyboard, disable_web_page_preview=True)

    elif call.data == "previous_1":
        await call.message.edit_text("<b>Here are the Smart-Util Options: 👇</b>", parse_mode=ParseMode.HTML, reply_markup=main_menu_keyboard, disable_web_page_preview=True)

    elif call.data == "previous_2":
        await call.message.edit_text("<b>Here are the Smart-Util Options: 👇</b>", parse_mode=ParseMode.HTML, reply_markup=second_menu_keyboard, disable_web_page_preview=True)

    elif call.data == "previous_3":
        await call.message.edit_text("<b>Here are the Smart-Util Options: 👇</b>", parse_mode=ParseMode.HTML, reply_markup=third_menu_keyboard, disable_web_page_preview=True)

    elif call.data == "close":
        await call.message.delete()

    elif call.data == "start_message":
        full_name_raw = f"{call.from_user.first_name} {call.from_user.last_name or ''}".strip()
        full_name_escaped = html.escape(full_name_raw)
        start_message = (
            f"<b>Hi {full_name_escaped}! Welcome To This Bot</b>\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>Smart Util</b> is your ultimate toolkit on Telegram, packed with AI tools, "
            f"educational resources, downloaders, temp mail, crypto utilities, and more. "
            f"Simplify your tasks with ease!\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>Don't forget to <a href=\"{UPDATE_CHANNEL_URL}\">join here</a> for updates!</b>"
        )
        start_buttons = SmartButtons()
        start_buttons.button(text="⚙️ Main Menu", callback_data="main_menu", position="header")
        start_buttons.button(text="ℹ️ About Me", callback_data="about_me")
        start_buttons.button(text="📄 Policy & Terms", callback_data="policy_terms")
        start_buttons = start_buttons.build_menu(b_cols=2, h_cols=1, f_cols=1)
        await call.message.edit_text(
            text=start_message,
            parse_mode=ParseMode.HTML,
            reply_markup=start_buttons,
            disable_web_page_preview=True
        )

    elif call.data == "policy_terms":
        policy_terms_text = (
            f"<b>📜 Policy & Terms Menu</b>\n\n"
            f"At <b>Smart Util ⚙️</b>, we prioritize your privacy and security. To ensure a seamless and safe experience, we encourage you to review our <b>Privacy Policy</b> and <b>Terms & Conditions</b>.\n\n"
            f"🔹 <b>Privacy Policy</b>: Learn how we collect, use, and protect your personal data.\n"
            f"🔹 <b>Terms & Conditions</b>: Understand the rules and guidelines for using our services.\n\n"
            f"✅ Staying informed helps you make the most of <b>Smart Util ⚙️</b> while ensuring compliance with our policies.\n\n"
            f"<b>💡 Choose an option below to proceed:</b>"
        )
        policy_terms_button = SmartButtons()
        policy_terms_button.button(text="Privacy Policy", callback_data="privacy_policy")
        policy_terms_button.button(text="Terms & Conditions", callback_data="terms_conditions")
        policy_terms_button.button(text="⬅️ Back", callback_data="start_message")
        policy_terms_button = policy_terms_button.build_menu(b_cols=2, h_cols=1, f_cols=1)
        await call.message.edit_text(policy_terms_text, parse_mode=ParseMode.HTML, reply_markup=policy_terms_button, disable_web_page_preview=True)

    elif call.data == "privacy_policy":
        privacy_policy_text = (
            f"<b>📜 Privacy Policy for Smart Util</b>\n\n"
            f"Welcome to <b>Smart Util</b> Bot. By using our services, you agree to this privacy policy.\n\n"
            f"<b>1. Information We Collect:</b>\n"
            f"   - <b>Personal Information:</b> User ID and username for personalization.\n"
            f"   - <b>Usage Data:</b> Information on how you use the app to improve our services.\n\n"
            f"<b>2. Usage of Information:</b>\n"
            f"   - <b>Service Enhancement:</b> To provide and improve <b>Smart Util</b>.\n"
            f"   - <b>Communication:</b> Updates and new features.\n"
            f"   - <b>Security:</b> To prevent unauthorized access.\n"
            f"   - <b>Advertisements:</b> Display of promotions.\n\n"
            f"<b>3. Data Security:</b>\n"
            f"   - These tools do not store any data, ensuring your privacy.\n"
            f"   - We use strong security measures, although no system is 100% secure.\n\n"
            f"Thank you for using <b>Smart Util</b>. We prioritize your privacy and security."
        )
        back_button = SmartButtons()
        back_button.button(text="⬅️ Back", callback_data="policy_terms")
        back_button = back_button.build_menu(b_cols=1, h_cols=1, f_cols=1)
        await call.message.edit_text(privacy_policy_text, parse_mode=ParseMode.HTML, reply_markup=back_button, disable_web_page_preview=True)

    elif call.data == "terms_conditions":
        dev_name = html.escape("ᴀʙɪʀ ᴀʀᴀꜰᴀᴛ ᴄʜᴀᴡᴅʜᴜʀʏ </🇧🇩>")
        terms_conditions_text = (
            f"<b>📜 Terms & Conditions for Smart Util</b>\n\n"
            f"Welcome to <b>Smart Util</b>. By using our services, you accept these <b>Terms & Conditions</b>.\n\n"
            f"<b>1. Usage Guidelines</b>\n"
            f"   - <b>Eligibility:</b> Must be 13 years of age or older.\n"
            f"   - This bot fully complies with Telegram’s <a href=\"https://telegram.org/tos/bot-developers\">Terms Of Service</a>\n\n"
            f"<b>2. Prohibited</b>\n"
            f"   - Illegal and unauthorized usage is strictly forbidden.\n"
            f"   - Spamming, abuse, or any kind of misuse is not tolerated.\n\n"
            f"<b>3. Tools and Usage</b>\n"
            f"   - For testing/development purposes only — not intended for unlawful activities.\n"
            f"   - We do not support misuse, fraud, or any policy-violating behavior.\n"
            f"   - Automated actions may result in rate limits or suspension.\n"
            f"   - We are not liable for account bans or misuse of tools.\n\n"
            f"<b>4. User Responsibility</b>\n"
            f"   - Users are responsible for how they use the bot.\n"
            f"   - Activities must comply with Telegram and legal policies.\n\n"
            f"<b>5. Disclaimer of Warranties</b>\n"
            f"   - No guarantee of uptime, accuracy, or data reliability.\n"
            f"   - We are not responsible for any misuse or its consequences.\n\n"
            f"<b>6. Termination</b>\n"
            f"   - Violations may lead to user ban or service suspension without prior notice.\n\n"
            f"<b>7. Contact Information</b>\n"
            f"   - For concerns, contact  <a href=\"https://t.me/ISmartCoder\">{dev_name}</a>\n\n"
            f"Thank you for using <b>Smart Util</b>. Your privacy, safety, and experience matter most. 🚀"
        )
        back_button = SmartButtons()
        back_button.button(text="⬅️ Back", callback_data="policy_terms")
        back_button = back_button.build_menu(b_cols=1, h_cols=1, f_cols=1)
        await call.message.edit_text(terms_conditions_text, parse_mode=ParseMode.HTML, reply_markup=back_button, disable_web_page_preview=True)