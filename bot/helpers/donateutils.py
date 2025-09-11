# Copyright @ISmartCoder
# SmartUtilBot - Telegram Utility Bot for Smart Features Bot
# Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack>
import hashlib
import time
import asyncio
import uuid
from typing import Dict, Any, Optional
from aiogram import Bot
from aiogram.types import Message, CallbackQuery, LabeledPrice, PreCheckoutQuery, SuccessfulPayment
from aiogram.enums import ParseMode
from aiogram.filters import BaseFilter
from aiogram.exceptions import TelegramBadRequest
from bot import dp
from bot.helpers.utils import new_task
from bot.helpers.botutils import send_message, get_args, delete_messages
from bot.helpers.notify import Smart_Notify
from bot.helpers.logger import LOGGER
from bot.helpers.buttons import SmartButtons
from bot.helpers.defend import SmartDefender
from config import OWNER_ID, DEVELOPER_USER_ID

DONATION_OPTIONS_TEXT = """
<b>Why support Smart Util?</b>
<b>━━━━━━━━━━━━━━━━━━</b>
🌟 <b>Love the service?</b>
Your support helps keep <b>SmartUtil</b> fast, reliable, and free for everyone.
Even a small <b>Gift or Donation</b> makes a big difference! 💖

👇 <b>Choose an amount to contribute:</b>

<b>Why contribute?</b>
More support = more motivation
More motivation = better tools
Better tools = more productivity
More productivity = less wasted time
Less wasted time = more done with <b>Smart Util</b> 💡
<b>More Muhahaha… 🤓🔥</b>
"""

PAYMENT_SUCCESS_TEXT = """
<b>✅ Donation Successful!</b>

🎉 Huge thanks <b>{0}</b> for donating <b>{1}</b> ⭐️ to support <b>Smart Util!</b>
Your contribution helps keep everything running smooth and awesome 🚀

<b>🧾 Transaction ID:</b> <code>{2}</code>
"""

ADMIN_NOTIFICATION_TEXT = """
<b>Hey New Donation Received 🤗</b>
<b>━━━━━━━━━━━━━━━</b>
<b>From: </b> {0}
<b>Username:</b> {2}
<b>UserID:</b> <code>{1}</code>
<b>Amount:</b> {3} ⭐️
<b>Transaction ID:</b> <code>{4}</code>
<b>━━━━━━━━━━━━━━━</b>
<b>Click Below Button If Need Refund 💸</b>
"""

INVOICE_CREATION_TEXT = "Generating invoice for {0} Stars...\nPlease wait ⏳"
INVOICE_CONFIRMATION_TEXT = "<b>✅ Invoice for {0} Stars has been generated! You can now proceed to pay via the button below.</b>"
DUPLICATE_INVOICE_TEXT = "<b>🚫 Wait Bro! Contribution Already in Progress!</b>"
INVALID_INPUT_TEXT = "<b>❌ Sorry Bro! Invalid Input! Use a positive number.</b>"
INVOICE_FAILED_TEXT = "<b>❌ Invoice Creation Failed, Bruh! Try Again!</b>"
PAYMENT_FAILED_TEXT = "<b>❌ Sorry Bro! Payment Declined! Contact Support!</b>"
REFUND_SUCCESS_TEXT = "<b>✅ Refund Successfully Completed Bro!</b>\n\n<b>{0} Stars</b> have been refunded to <b><a href='tg://user?id={2}'>{1}</a></b>"
REFUND_FAILED_TEXT = "<b>❌ Refund Failed!</b>\n\nFailed to refund <b>{0} Stars</b> to <b>{1}</b> (ID: <code>{2}</code>)\nError: {3}"

active_invoices = {}

payment_data = {}

def timeof_fmt(seconds):
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    return f"{int(days)}d {int(hours)}h {int(minutes)}m {int(seconds)}s"
    
def get_donation_buttons(amount: int = 5):
    buttons = SmartButtons()
    if amount == 5:
        buttons.button(f"{amount} ⭐️", callback_data=f"donate_{amount}")
        buttons.button("+5", callback_data=f"increment_donate_{amount}")
    else:
        buttons.button("-5", callback_data=f"decrement_donate_{amount}")
        buttons.button(f"{amount} ⭐️", callback_data=f"donate_{amount}")
        buttons.button("+5", callback_data=f"increment_donate_{amount}")
    buttons.button("🔙 Back", callback_data="about_me")
    return buttons.build_menu(b_cols=2 if amount == 5 else 3, h_cols=1, f_cols=1)

async def generate_invoice(bot: Bot, chat_id: int, user_id: int, quantity: int, message_id: int):
    if active_invoices.get(user_id):
        await send_message(chat_id, DUPLICATE_INVOICE_TEXT, parse_mode=ParseMode.HTML)
        return
    back_buttons = SmartButtons()
    back_buttons.button("🔙 Back", callback_data="about_me")
    back_button = back_buttons.build_menu(b_cols=1, h_cols=1, f_cols=1)
    try:
        active_invoices[user_id] = True
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8]
        invoice_payload = f"contribution_{user_id}_{quantity}_{timestamp}_{unique_id}"
        title = "Support Smart Util"
        description = f"Contribute {quantity} Stars to support ongoing development and keep the tools free, fast, and reliable for everyone 💫 Every star helps us grow!"
        currency = "XTR"
        prices = [LabeledPrice(label=f"⭐️ {quantity} Stars", amount=quantity)]
        pay_buttons = SmartButtons()
        pay_buttons.button("💫 Donate Via Stars", pay=True)
        pay_button = pay_buttons.build_menu(b_cols=1)
        await bot.send_invoice(
            chat_id=chat_id,
            title=title,
            description=description,
            payload=invoice_payload,
            provider_token="",
            currency=currency,
            prices=prices,
            start_parameter="donate-stars-to-smartutil",
            reply_markup=pay_button
        )
        await bot.edit_message_text(
            text=INVOICE_CONFIRMATION_TEXT.format(quantity),
            chat_id=chat_id,
            message_id=message_id,
            parse_mode=ParseMode.HTML,
            reply_markup=back_button
        )
        LOGGER.info(f"✅ Invoice sent for {quantity} stars to user {user_id} with payload {invoice_payload}")
    except Exception as e:
        LOGGER.error(f"❌ Failed to generate invoice for user {user_id}: {str(e)}")
        try:
            await bot.edit_message_text(
                text=INVOICE_FAILED_TEXT,
                chat_id=chat_id,
                message_id=message_id,
                parse_mode=ParseMode.HTML,
                reply_markup=back_button
            )
        except TelegramBadRequest as edit_e:
            LOGGER.error(f"Failed to edit message in chat {chat_id}: {str(edit_e)}")
            await send_message(
                chat_id=chat_id,
                text=INVOICE_FAILED_TEXT,
                parse_mode=ParseMode.HTML,
                reply_markup=back_button
            )
    finally:
        active_invoices.pop(user_id, None)

class DonateCallbackFilter(BaseFilter):
    async def __call__(self, callback_query: CallbackQuery):
        return callback_query.data and (
            callback_query.data.startswith(("donate_", "increment_donate_", "decrement_donate_", "refund_")) or
            callback_query.data == "donate"
        )

@dp.callback_query(DonateCallbackFilter())
@new_task
@SmartDefender
async def handle_donate_callback(callback_query: CallbackQuery, bot: Bot):
    data = callback_query.data
    chat_id = callback_query.message.chat.id
    user_id = callback_query.from_user.id
    message_id = callback_query.message.message_id
    LOGGER.info(f"Callback query received: data={data}, user: {user_id}, chat: {chat_id}")
    try:
        if data == "donate":
            reply_markup = get_donation_buttons()
            await callback_query.message.edit_text(
                text=DONATION_OPTIONS_TEXT,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
            await callback_query.answer()
            LOGGER.info(f"Showed donation options to user {user_id}")
        elif data.startswith("donate_"):
            quantity = int(data.split("_")[1])
            await bot.edit_message_text(
                text=INVOICE_CREATION_TEXT.format(quantity),
                chat_id=chat_id,
                message_id=message_id,
                parse_mode=ParseMode.HTML
            )
            await generate_invoice(bot, chat_id, user_id, quantity, message_id)
            await callback_query.answer("✅ Invoice Generated! Donate Now! ⭐️")
        elif data.startswith("increment_donate_"):
            current_amount = int(data.split("_")[2])
            new_amount = current_amount + 5
            reply_markup = get_donation_buttons(new_amount)
            await callback_query.message.edit_text(
                text=DONATION_OPTIONS_TEXT,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
            await callback_query.answer(f"Updated to {new_amount} Stars")
            LOGGER.info(f"Incremented donation amount to {new_amount} for user {user_id}")
        elif data.startswith("decrement_donate_"):
            current_amount = int(data.split("_")[2])
            new_amount = max(5, current_amount - 5)
            reply_markup = get_donation_buttons(new_amount)
            await callback_query.message.edit_text(
                text=DONATION_OPTIONS_TEXT,
                parse_mode=ParseMode.HTML,
                reply_markup=reply_markup
            )
            await callback_query.answer(f"Updated to {new_amount} Stars")
            LOGGER.info(f"Decremented donation amount to {new_amount} for user {user_id}")
        elif data.startswith("refund_"):
            admin_ids = OWNER_ID if isinstance(OWNER_ID, (list, tuple)) else [OWNER_ID]
            if user_id in admin_ids or user_id == DEVELOPER_USER_ID:
                payment_id = data.replace("refund_", "")
                user_info = payment_data.get(payment_id)
                if not user_info:
                    await callback_query.answer("❌ Payment data not found!", show_alert=True)
                    return
                refund_user_id = user_info['user_id']
                refund_amount = user_info['amount']
                full_charge_id = user_info['charge_id']
                full_name = user_info['full_name']
                try:
                    result = await bot.refund_star_payment(refund_user_id, full_charge_id)
                    if result:
                        await callback_query.message.edit_text(
                            text=REFUND_SUCCESS_TEXT.format(refund_amount, full_name, refund_user_id),
                            parse_mode=ParseMode.HTML
                        )
                        await callback_query.answer("✅ Refund processed successfully!")
                        payment_data.pop(payment_id, None)
                        LOGGER.info(f"Successfully refunded {refund_amount} stars to user {refund_user_id}")
                    else:
                        await callback_query.answer("❌ Refund failed!", show_alert=True)
                        LOGGER.error(f"Refund failed for user {refund_user_id}")
                except Exception as e:
                    LOGGER.error(f"❌ Refund failed for user {refund_user_id}: {str(e)}")
                    await Smart_Notify(bot, "donate", e, callback_query.message)
                    await callback_query.message.edit_text(
                        text=REFUND_FAILED_TEXT.format(refund_amount, full_name, refund_user_id, str(e)),
                        parse_mode=ParseMode.HTML
                    )
                    await callback_query.answer("❌ Refund failed!", show_alert=True)
            else:
                await callback_query.answer("❌ You don't have permission to refund!", show_alert=True)
                LOGGER.warning(f"Unauthorized refund attempt by user {user_id}")
    except Exception as e:
        LOGGER.error(f"Error processing donation callback in chat {chat_id}: {str(e)}")
        await Smart_Notify(bot, "donate", e, callback_query.message)
        await callback_query.answer("❌ Sorry Bro! Donation System Error", show_alert=True)

@dp.pre_checkout_query()
@new_task
@SmartDefender
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery, bot: Bot):
    try:
        await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)
        LOGGER.info(f"✅ Pre-checkout query {pre_checkout_query.id} OK for user {pre_checkout_query.from_user.id}")
    except Exception as e:
        LOGGER.error(f"❌ Pre-checkout query {pre_checkout_query.id} failed: {str(e)}")
        await bot.answer_pre_checkout_query(
            pre_checkout_query.id,
            ok=False,
            error_message="Failed to process pre-checkout."
        )

@dp.message(lambda message: message.successful_payment)
@new_task
@SmartDefender
async def process_successful_payment(message: Message, bot: Bot):
    payment = message.successful_payment
    user_id = message.from_user.id
    chat_id = message.chat.id
    LOGGER.info(f"Processing successful payment for user {user_id} in chat {chat_id}")
    try:
        user = message.from_user
        full_name = f"{user.first_name} {getattr(user, 'last_name', '')}".strip() or "Unknown" if user else "Unknown"
        username = f"@{user.username}" if user and user.username else "@N/A"
        payment_id = str(uuid.uuid4())[:16]
        payment_data[payment_id] = {
            'user_id': user_id,
            'full_name': full_name,
            'username': username,
            'amount': payment.total_amount,
            'charge_id': payment.telegram_payment_charge_id
        }
        success_buttons = SmartButtons()
        success_buttons.button("Transaction ID", copy_text=payment.telegram_payment_charge_id)
        success_message = success_buttons.build_menu()
        await send_message(
            chat_id=chat_id,
            text=PAYMENT_SUCCESS_TEXT.format(full_name, payment.total_amount, payment.telegram_payment_charge_id),
            parse_mode=ParseMode.HTML,
            reply_markup=success_message
        )
        admin_text = ADMIN_NOTIFICATION_TEXT.format(full_name, user_id, username, payment.total_amount, payment.telegram_payment_charge_id)
        refund_buttons = SmartButtons()
        refund_buttons.button(f"Refund {payment.total_amount} ⭐️", callback_data=f"refund_{payment_id}")
        refund_button = refund_buttons.build_menu()
        admin_ids = OWNER_ID if isinstance(OWNER_ID, (list, tuple)) else [OWNER_ID]
        if DEVELOPER_USER_ID not in admin_ids:
            admin_ids.append(DEVELOPER_USER_ID)
        for admin_id in admin_ids:
            try:
                await send_message(
                    chat_id=admin_id,
                    text=admin_text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=refund_button
                )
            except Exception as e:
                LOGGER.error(f"❌ Failed to notify admin {admin_id}: {str(e)}")
        LOGGER.info(f"Successfully processed payment for user {user_id}: {payment.total_amount} stars")
    except Exception as e:
        LOGGER.error(f"❌ Payment processing failed for user {user_id if user_id else 'unknown'}: {str(e)}")
        await Smart_Notify(bot, "donate", e, message)
        support_buttons = SmartButtons()
        support_buttons.button("📞 Contact Support", url=f"tg://user?id={DEVELOPER_USER_ID}")
        support_markup = support_buttons.build_menu()
        await send_message(
            chat_id=chat_id,
            text=PAYMENT_FAILED_TEXT,
            parse_mode=ParseMode.HTML,
            reply_markup=support_markup
        )

