import os
import time
import subprocess
from datetime import datetime, timedelta
import psutil
from pyrogram import filters
from pyrogram.enums import ParseMode
from bot.config import UPDATE_CHANNEL_URL
from bot.core import SmartUsers
from bot.helpers import LOGGER, SmartButtons, send_message, main_menu_keyboard, second_menu_keyboard, third_menu_keyboard, responses, DONATION_OPTIONS_TEXT, get_donation_buttons, generate_invoice, handle_donate_callback, timeof_fmt

async def SmartCallback(client, callback_query):
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
            f"**Smart Bot Status ⇾ Report ✅**\n"
            f"**━━━━━━━━━━━━━━━━**\n"
            f"**Users & Groups Engagements:**\n"
            f"**1 Day:** {daily_users} users were active\n"
            f"**1 Week:** {weekly_users} users were active\n"
            f"**1 Month:** {monthly_users} users were active\n"
            f"**1 Year:** {yearly_users} users were active\n"
            f"**Total Connected Groups:** {total_groups}\n"
            f"**━━━━━━━━━━━━━━━━**\n"
            f"**Total Smart Tools Users:** {total_users} ✅"
        )
        back_button = SmartButtons()
        back_button.button("⬅️ Back", callback_data="fstats")
        await call.message.edit_text(stats_text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_button.build_menu(b_cols=1))
        return
  
    if call.data == "fstats":
        stats_dashboard_text = (
            """**🗒 Smart Tool Basic Statistics Menu 🔍**
**━━━━━━━━━━━━━━━━━**
Stay Updated With Real Time Insights....⚡️
⊗ **Full Statistics:** Get Full Statistics Of Smart Tool ⚙️
⊗ **Top Users:** Get Top User's Leaderboard 🔥
⊗ **Growth Trends:** Get Knowledge About Growth 👁
⊗ **Activity Times:** See Which User Is Most Active ⏰
⊗ **Milestones:** Track Special Achievements 🏅
**━━━━━━━━━━━━━━━━━**
**💡 Select an option and take control:**
"""
        )
        stats_dashboard_buttons = SmartButtons()
        stats_dashboard_buttons.button("📈 Usage Report", callback_data="stats")
        stats_dashboard_buttons.button("🏆 Top Users", callback_data="top_users_1")
        stats_dashboard_buttons.button("⬅️ Back", callback_data="about_me")
        await call.message.edit_text(stats_dashboard_text, parse_mode=ParseMode.MARKDOWN, reply_markup=stats_dashboard_buttons.build_menu(b_cols=2))
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
            f"**🏆 Top Users (All-time) — page {page}/{total_pages if total_pages > 0 else 1}:**\n"
            f"**━━━━━━━━━━━━━━━**\n"
        )
        for i, user in enumerate(paginated_users, start=start_index + 1):
            user_id = user['user_id']
            try:
                telegram_user = await client.get_users(user_id)
                full_name = f"{telegram_user.first_name} {telegram_user.last_name}" if telegram_user.last_name else telegram_user.first_name
            except Exception as e:
                LOGGER.error(f"Failed to fetch user {user_id}: {e}")
                full_name = f"User_{user_id}"
            rank_emoji = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "🔸"
            top_users_text += f"**{rank_emoji} {i}.** [{full_name}](tg://user?id={user_id})\n** - User Id :** `{user_id}`\n\n"
      
        buttons = SmartButtons()
        if page == 1 and total_pages > 1:
            buttons.button("Next ➡️", callback_data=f"top_users_{page+1}")
            buttons.button("⬅️ Back", callback_data="fstats")
        elif page > 1 and page < total_pages:
            buttons.button("⬅️ Previous", callback_data=f"top_users_{page-1}")
            buttons.button("Next ➡️", callback_data=f"top_users_{page+1}")
        elif page == total_pages and page > 1:
            buttons.button("⬅️ Previous", callback_data=f"top_users_{page-1}")
        else:
            buttons.button("⬅️ Back", callback_data="fstats")
      
        await call.message.edit_text(top_users_text, parse_mode=ParseMode.MARKDOWN, reply_markup=buttons.build_menu(b_cols=2))
        return
  
    if call.data == "server":
        ping_output = subprocess.getoutput("ping -c 1 google.com")
        ping = ping_output.split("time=")[1].split()[0] if "time=" in ping_output else "N/A"
        disk = psutil.disk_usage('/')
        total_disk = disk.total / (2**30)
        used_disk = disk.used / (2**30)
        free_disk = disk.free / (2**30)
        mem = psutil.virtual_memory()
        boot_time = psutil.boot_time()
        uptime_seconds = time.time() - boot_time
        uptime = timeof_fmt(upptime_seconds)
        swap = psutil.swap_memory()
        total_mem = mem.total / (2**30)
        used_mem = mem.used / (2**30)
        available_mem = mem.available / (2**30)
        server_status_text = (
            f"**Smart Bot Status ⇾ Report ✅**\n"
            f"**━━━━━━━━━━━━━**\n"
            f"**Server Connection:**\n"
            f"**- Ping:** {ping} ms\n"
            f"**- Bot Status:** Online\n"
            f"**- Server Uptime:** {uptime}\n"
            f"**━━━━━━━━━━━━━**\n"
            f"**Server Storage:**\n"
            f"**- Total:** {total_disk:.2f} GB\n"
            f"**- Used:** {used_disk:.2f} GB\n"
            f"**- Available:** {free_disk:.2f} GB\n"
            f"**━━━━━━━━━━━━━**\n"
            f"**Memory Usage:**\n"
            f"**- Total:** {total_mem:.2f} GB\n"
            f"**- Used:** {used_mem:.2f} GB\n"
            f"**- Available:** {available_mem:.2f} GB\n"
            f"**━━━━━━━━━━━━━**\n"
            f"**Server Stats Check Successful ✅**"
        )
        back_button = SmartButtons()
        back_button.button("⬅️ Back", callback_data="about_me")
        await call.message.edit_text(server_status_text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_button.build_menu(b_cols=1))
        return
  
    if call.data in responses:
        if call.data == "server":
            back_button = SmartButtons()
            back_button.button("⬅️ Back", callback_data="about_me")
        elif call.data == "stats":
            back_button = SmartButtons()
            back_button.button("⬅️ Back", callback_data="fstats")
        elif call.data == "about_me":
            back_button = SmartButtons()
            back_button.button("📊 Statistics", callback_data="fstats")
            back_button.button("💾 Server", callback_data="server")
            back_button.button("⭐️ Donate", callback_data="donate")
            back_button.button("⬅️ Back", callback_data="start_message")
        elif call.data in ["ai_tools", "credit_cards", "crypto", "converter", "coupons", "decoders", "downloaders", "domain_check", "education_utils", "rembg"]:
            back_button = SmartButtons()
            back_button.button("Back", callback_data="main_menu")
        elif call.data in ["file_to_link", "github", "info", "network_tools", "random_address", "string_session", "stripe_keys", "sticker", "time_date", "text_split"]:
            back_button = SmartButtons()
            back_button.button("Back", callback_data="second_menu")
        elif call.data in ["tempmail", "text_ocr", "bot_users_export", "web_capture", "weather", "yt_tools", "translate"]:
            back_button = SmartButtons()
            back_button.button("Back", callback_data="third_menu")
        else:
            back_button = SmartButtons()
            back_button.button("Back", callback_data="main_menu")
      
        await call.message.edit_text(
            responses[call.data][0],
            parse_mode=responses[call.data][1]['parse_mode'],
            disable_web_page_preview=responses[call.data][1]['disable_web_page_preview'],
            reply_markup=back_button.build_menu(b_cols=1 if call.data in ["server", "stats"] else 2 if call.data == "about_me" else 1)
        )
    elif call.data.startswith("donate_") or call.data.startswith("increment_donate_") or call.data.startswith("decrement_donate_") or call.data == "donate":
        await handle_donate_callback(client, call)
    elif call.data == "main_menu":
        await call.message.edit_text("<b>Here are the Smart-Tool Options: 👇</b>", parse_mode=ParseMode.HTML, reply_markup=main_menu_keyboard)
    elif call.data == "next_1":
        await call.message.edit_text("<b>Here are the Smart-Tool Options: 👇</b>", parse_mode=ParseMode.HTML, reply_markup=second_menu_keyboard)
    elif call.data == "next_2":
        await call.message.edit_text("<b>Here are the Smart-Tool Options: 👇</b>", parse_mode=ParseMode.HTML, reply_markup=third_menu_keyboard)
    elif call.data == "previous_1":
        await call.message.edit_text("<b>Here are the Smart-Tool Options: 👇</b>", parse_mode=ParseMode.HTML, reply_markup=main_menu_keyboard)
    elif call.data == "previous_2":
        await call.message.edit_text("<b>Here are the Smart-Tool Options: 👇</b>", parse_mode=ParseMode.HTML, reply_markup=second_menu_keyboard)
    elif call.data == "close":
        await call.message.delete()
    elif call.data == "start_message":
        full_name = f"{call.from_user.first_name} {call.from_user.last_name}" if call.from_user.last_name else call.from_user.first_name
        start_message = (
            f"<b>Hi {full_name}! Welcome To This Bot</b>\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>Smart Tool</b> The ultimate toolkit on Telegram, offering education, AI, downloaders, temp mail, credit card tool, and more. Simplify your tasks with ease!\n"
            f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>Don't Forget To <a href='{UPDATE_CHANNEL_URL}'>Join Here</a> For Updates!</b>"
        )
        back_button = SmartButtons()
        back_button.button("⚙️ Main Menu", callback_data="main_menu")
        back_button.button("ℹ️ About Me", callback_data="about_me")
        back_button.button("📄 Policy & Terms", callback_data="policy_terms")
        await call.message.edit_text(
            start_message,
            parse_mode=ParseMode.HTML,
            reply_markup=back_button.build_menu(b_cols=2),
            disable_web_page_preview=True
        )
    elif call.data == "policy_terms":
        policy_terms_text = (
            f"<b>📜 Policy & Terms Menu</b>\n\n"
            f"At <b>Smart Tool ⚙️</b>, we prioritize your privacy and security. To ensure a seamless and safe experience, we encourage you to review our <b>Privacy Policy</b> and <b>Terms & Conditions</b>.\n\n"
            f"🔹 <b>Privacy Policy</b>: Learn how we collect, use, and protect your personal data.\n"
            f"🔹 <b>Terms & Conditions</b>: Understand the rules and guidelines for using our services.\n\n"
            f"<b>💡 Choose an option below to proceed:</b>"
        )
        policy_terms_button = SmartButtons()
        policy_terms_button.button("Privacy Policy", callback_data="privacy_policy")
        policy_terms_button.button("Terms & Conditions", callback_data="terms_conditions")
        policy_terms_button.button("⬅️ Back", callback_data="start_message")
        await call.message.edit_text(policy_terms_text, parse_mode=ParseMode.HTML, reply_markup=policy_terms_button.build_menu(b_cols=2))
    elif call.data == "privacy_policy":
        privacy_policy_text = (
            f"<b>📜 Privacy Policy for Smart Tool ⚙️</b>\n\n"
            f"Welcome to <b>Smart Tool ⚙️</b> Bot. By using our services, you agree to this privacy policy.\n\n"
            f"1. <b>Personal Information</b>:\n"
            f" - Personal Information: User ID and username for personalization.\n"
            f" - <b>Usage Data</b>: Information on how you use the app to improve our services.\n\n"
            f"2. Usage of Information:\n"
            f" - <b>Service Enhancement</b>: To provide and improve <b>Smart Tool ⚙️</b>\n"
            f" - <b>Communication</b>: Updates and new features.\n"
            f" - <b>Security</b>: To prevent unauthorized access.\n"
            f" - <b>Advertisements</b>: Display of promotions.\n\n"
            f"3. Data Security:\n"
            f" - These tools do not store any data, ensuring your privacy.\n"
            f" - We use strong security measures, although no system is 100% secure.\n\n"
            f"Thank you for using <b>Smart Tool ⚙️</b>. We prioritize your privacy and security."
        )
        back_button = SmartButtons()
        back_button.button("⬅️ Back", callback_data="policy_terms")
        await call.message.edit_text(privacy_policy_text, parse_mode=ParseMode.HTML, reply_markup=back_button.build_menu(b_cols=1))
    elif call.data == "terms_conditions":
        terms_conditions_text = (
            f"<b>📜 Terms & Conditions for Smart Tool ⚙️</b>\n\n"
            f"Welcome to <b>Smart Tool ⚙️</b>. By using our services, you accept these <b>Terms & Conditions</b>.\n\n"
            f"<b>1. Usage Guidelines</b>\n"
            f" - Eligibility: Must be 13 years of age or older.\n\n"
            f"<b>2. Prohibited</b>\n"
            f" - Illegal and unauthorized uses are strictly forbidden.\n"
            f" - Spamming and abusing are not allowed in this Bot\n\n"
            f"<b>3. Tools and Usage</b>\n"
            f" - For testing/development purposes only, not for illegal use.\n"
            f" - We <b>do not support</b> misuse for fraud or policy violations.\n"
            f" - Automated requests may lead to service limitations or suspension.\n"
            f" - We are not responsible for any account-related issues.\n\n"
            f"<b>4. User Responsibility</b>\n"
            f" - You are responsible for all activities performed using the bot.\n"
            f" - Ensure that your activities comply with platform policies.\n\n"
            f"<b>5. Disclaimer of Warranties</b>\n"
            f" - We do not guarantee uninterrupted service, accuracy, or reliability.\n"
            f" - We are not responsible for any consequences arising from your use of the bot.\n\n"
            f"<b>6. Termination</b>\n"
            f" - Access may be terminated for any violations without prior notice.\n\n"
            f"<b>7. Contact Information</b>\n"
            f" - Contact My Dev for any inquiries or concerns. <a href='tg://user?id=7303810912'>Abir Arafat Chawdhury👨‍💻</a> \n\n"
            f"Thank you for using <b>Smart Tool ⚙️</b>. We prioritize your safety, security, and best user experience. 🚀"
        )
        back_button = SmartButtons()
        back_button.button("⬅️ Back", callback_data="policy_terms")
        await call.message.edit_text(terms_conditions_text, parse_mode=ParseMode.HTML, reply_markup=back_button.build_menu(b_cols=1))
    elif call.data == "second_menu":
        await call.message.edit_text("<b>Here are the Smart-Tool Options: 👇</b>", parse_mode=ParseMode.HTML, reply_markup=second_menu_keyboard)
    elif call.data == "third_menu":
        await call.message.edit_text("<b>Here are the Smart-Tool Options: 👇</b>", parse_mode=ParseMode.HTML, reply_markup=third_menu_keyboard)