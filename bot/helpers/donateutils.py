import logging
import uuid
import time
from bot import SmartGram
from bot.helpers import LOGGER, SmartButtons, send_message
from pyrogram import filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, LabeledPrice
from pyrogram.raw.functions.messages import SetBotPrecheckoutResults, SetBotShippingResults
from pyrogram.raw.types import (
    UpdateBotPrecheckoutQuery,
    UpdateBotShippingQuery,
    UpdateNewMessage,
    MessageService,
    MessageActionPaymentSentMe,
    PeerUser,
    PeerChat,
    PeerChannel
)
from pyrogram.enums import ParseMode
from ..config import OWNER_ID, DEVELOPER_USER_ID, UPDATE_CHANNEL_URL

logger = LOGGER

DONATION_OPTIONS_TEXT = """
**Why support Smart Tools?**
**━━━━━━━━━━━━━━━━━━**
🌟 **Love the service?**
Your support helps keep **SmartTools** fast, reliable, and free for everyone.
Even a small **Gift or Donation** makes a big difference! 💖
👇 **Choose an amount to contribute:**
**Why contribute?**
More support = more motivation
More motivation = better tools
Better tools = more productivity
More productivity = less wasted time
Less wasted time = more done with **Smart Tools** 💡
**More Muhahaha… 🤓🔥**
**🔔 For Bot Update News**: <a href='{UPDATE_CHANNEL_URL}'>Join Now</a>
""".format(UPDATE_CHANNEL_URL=UPDATE_CHANNEL_URL)

PAYMENT_SUCCESS_TEXT = """
**✅ Donation Successful!**
🎉 Huge thanks **{0}** for donating **{1}** ⭐️ to support **Smart Tool!**
Your contribution helps keep everything running smooth and awesome 🚀
**🧾 Transaction ID:** `{2}`
"""

ADMIN_NOTIFICATION_TEXT = """
**Hey New Donation Received 🤗**
**━━━━━━━━━━━━━━━**
**From: ** {0}
**Username:** {2}
**UserID:** `{1}`
**Amount:** {3} ⭐️
**Transaction ID:** `{4}`
**━━━━━━━━━━━━━━━**
**Click Below Button If Need Refund 💸**
"""

INVOICE_CREATION_TEXT = "Generating invoice for {0} Stars...\nPlease wait ⏳"
INVOICE_CONFIRMATION_TEXT = "**✅ Invoice for {0} Stars has been generated! You can now proceed to pay via the button below.**"
DUPLICATE_INVOICE_TEXT = "**🚫 Wait Bro! Contribution Already in Progress!**"
INVALID_INPUT_TEXT = "**❌ Sorry Bro! Invalid Input! Use a positive number.**"
INVOICE_FAILED_TEXT = "**❌ Invoice Creation Failed, Bruh! Try Again!**"
PAYMENT_FAILED_TEXT = "**❌ Sorry Bro! Payment Declined! Contact Support!**"
REFUND_SUCCESS_TEXT = "**✅ Refund Successfully Completed Bro!**\n\n**{0} Stars** have been refunded to **[{1}](tg://user?id={2})**"
REFUND_FAILED_TEXT = "**❌ Refund Failed!**\n\nFailed to refund **{0} Stars** to **{1}** (ID: `{2}`)\nError: {3}"

active_invoices = {}
payment_data = {}

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
    return buttons.build_menu(b_cols=2)

@SmartGram.on_callback_query(filters.regex(r"^(donate|donate_\d+|increment_donate_\d+|decrement_donate_\d+|show_donate_options|refund_.+)$"))
async def handle_donate_callback(client, callback_query: CallbackQuery):
    data = callback_query.data
    chat_id = callback_query.message.chat.id
    user_id = callback_query.from_user.id
    logger.info(f"Callback query received: data={data}, user: {user_id}, chat: {chat_id}")
    
    if data == "donate" or data == "show_donate_options":
        reply_markup = get_donation_buttons()
        await callback_query.message.edit_text(
            DONATION_OPTIONS_TEXT,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        await callback_query.answer()
    elif data.startswith("donate_"):
        quantity = int(data.split("_")[1])
        await generate_invoice(client, chat_id, user_id, quantity, is_callback=True, callback_query=callback_query)
    elif data.startswith("increment_donate_"):
        current_amount = int(data.split("_")[2])
        new_amount = current_amount + 5
        reply_markup = get_donation_buttons(new_amount)
        await callback_query.message.edit_text(
            DONATION_OPTIONS_TEXT,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        await callback_query.answer(f"Updated to {new_amount} Stars")
    elif data.startswith("decrement_donate_"):
        current_amount = int(data.split("_")[2])
        new_amount = max(5, current_amount - 5)
        reply_markup = get_donation_buttons(new_amount)
        await callback_query.message.edit_text(
            DONATION_OPTIONS_TEXT,
            parse_mode=ParseMode.HTML,
            reply_markup=reply_markup
        )
        await callback_query.answer(f"Updated to {new_amount} Stars")
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
                result = await client.refund_star_payment(refund_user_id, full_charge_id)
                if result:
                    await callback_query.message.edit_text(
                        REFUND_SUCCESS_TEXT.format(refund_amount, full_name, refund_user_id),
                        parse_mode=ParseMode.MARKDOWN
                    )
                    await callback_query.answer("✅ Refund processed successfully!")
                    payment_data.pop(payment_id, None)
                else:
                    await callback_query.answer("❌ Refund failed!", show_alert=True)
            except Exception as e:
                logger.error(f"❌ Refund failed for user {refund_user_id}: {str(e)}")
                await callback_query.message.edit_text(
                    REFUND_FAILED_TEXT.format(refund_amount, full_name, refund_user_id, str(e)),
                    parse_mode=ParseMode.MARKDOWN
                )
                await callback_query.answer("❌ Refund failed!", show_alert=True)
        else:
            await callback_query.answer("❌ You don't have permission to refund!", show_alert=True)

async def generate_invoice(client, chat_id: int, user_id: int, quantity: int, is_callback: bool = False, callback_query: CallbackQuery = None):
    if user_id in active_invoices:
        if is_callback:
            await callback_query.answer("Contribution already in progress!")
        else:
            await send_message(chat_id, DUPLICATE_INVOICE_TEXT, parse_mode=ParseMode.MARKDOWN)
        return
    active_invoices[user_id] = True
    back_button = SmartButtons()
    back_button.button("🔙 Back", callback_data="about_me")
    try:
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8]
        invoice_payload = f"contribution_{user_id}_{quantity}_{timestamp}_{unique_id}"
        title = "Support Smart Tools"
        description = f"Contribute {quantity} Stars to support ongoing development and keep the tools free, fast, and reliable for everyone 💫 Every star helps us grow!"
        currency = "XTR"
        prices = [LabeledPrice(label=f"⭐️ {quantity} Stars", amount=quantity)]
        reply_markup = SmartButtons()
        reply_markup.button_buy("💫 Donate Via Stars")
        if not is_callback:
            loading_message = await send_message(
                chat_id,
                INVOICE_CREATION_TEXT.format(quantity),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=back_button.build_menu(b_cols=1)
            )
        await client.send_invoice(
            chat_id=chat_id,
            title=title,
            description=description,
            payload=invoice_payload,
            currency=currency,
            prices=prices,
            start_parameter="donate-stars-to-smarttool",
            reply_markup=reply_markup.build_menu(b_cols=1)
        )
        if is_callback:
            await callback_query.message.edit_text(
                INVOICE_CONFIRMATION_TEXT.format(quantity),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=back_button.build_menu(b_cols=1)
            )
            await callback_query.answer("✅ Invoice Generated! Donate Now! ⭐️")
        else:
            await loading_message.edit_text(
                INVOICE_CONFIRMATION_TEXT.format(quantity),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=back_button.build_menu(b_cols=1)
            )
        logger.info(f"✅ Invoice sent for {quantity} stars to user {user_id} with payload {invoice_payload}")
    except Exception as e:
        logger.error(f"❌ Failed to generate invoice for user {user_id}: {str(e)}")
        await send_message(
            chat_id,
            INVOICE_FAILED_TEXT,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=back_button.build_menu(b_cols=1)
        )
        if is_callback:
            await callback_query.answer("Failed to create invoice.")
    finally:
        active_invoices.pop(user_id, None)

@SmartGram.on_raw_update()
async def raw_update_handler(client, update, users, chats):
    if isinstance(update, UpdateBotPrecheckoutQuery):
        try:
            await client.answer_pre_checkout_query(
                pre_checkout_query_id=update.query_id,
                success=True
            )
            logger.info(f"✅ Pre-checkout query {update.query_id} OK for user {update.user_id}")
        except Exception as e:
            logger.error(f"❌ Pre-checkout query {update.query_id} failed: {str(e)}")
            await client.answer_pre_checkout_query(
                pre_checkout_query_id=update.query_id,
                success=False,
                error="Failed to process pre-checkout."
            )
    elif isinstance(update, UpdateBotShippingQuery):
        try:
            await client.invoke(
                SetBotShippingResults(
                    query_id=update.query_id,
                    shipping_options=[]
                )
            )
            logger.info(f"✅ Shipping query {update.query_id} OK for user {update.user_id}")
        except Exception as e:
            logger.error(f"❌ Shipping query {update.query_id} failed: {str(e)}")
            await client.invoke(
                SetBotShippingResults(
                    query_id=update.query_id,
                    error="Shipping not needed for contributions."
                )
            )
    elif isinstance(update, UpdateNewMessage) and isinstance(update.message, MessageService) and isinstance(update.message.action, MessageActionPaymentSentMe):
        payment = update.message.action
        user_id = None
        chat_id = None
        try:
            if update.message.from_id and hasattr(update.message.from_id, 'user_id'):
                user_id = update.message.from_id.user_id
            elif users:
                possible_user_ids = [uid for uid in users if uid > 0]
                user_id = possible_user_ids[0] if possible_user_ids else None
            if not user_id:
                raise ValueError(f"Invalid user_id ({user_id})")
            if isinstance(update.message.peer_id, PeerUser):
                chat_id = update.message.peer_id.user_id
            elif isinstance(update.message.peer_id, PeerChat):
                chat_id = update.message.peer_id.chat_id
            elif isinstance(update.message.peer_id, PeerChannel):
                chat_id = update.message.peer_id.channel_id
            else:
                chat_id = user_id
            if not chat_id:
                raise ValueError(f"Invalid chat_id ({chat_id})")
            user = users.get(user_id) if users else None
            full_name = f"{user.first_name} {getattr(user, 'last_name', '')}".strip() or "Unknown" if user else "Unknown"
            username = f"@{user.username}" if user and user.username else "@N/A"
            payment_id = str(uuid.uuid4())[:16]
            payment_data[payment_id] = {
                'user_id': user_id,
                'full_name': full_name,
                'username': username,
                'amount': payment.total_amount,
                'charge_id': payment.charge.id
            }
            success_buttons = SmartButtons()
            success_buttons.button("Transaction ID", copy_text=payment.charge.id)
            await send_message(
                chat_id=chat_id,
                text=PAYMENT_SUCCESS_TEXT.format(full_name, payment.total_amount, payment.charge.id),
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=success_buttons.build_menu(b_cols=1)
            )
            admin_text = ADMIN_NOTIFICATION_TEXT.format(full_name, user_id, username, payment.total_amount, payment.charge.id)
            refund_buttons = SmartButtons()
            refund_buttons.button(f"Refund {payment.total_amount} ⭐️", callback_data=f"refund_{payment_id}")
            admin_ids = OWNER_ID if isinstance(OWNER_ID, (list, tuple)) else [OWNER_ID]
            if DEVELOPER_USER_ID not in admin_ids:
                admin_ids.append(DEVELOPER_USER_ID)
            for admin_id in admin_ids:
                try:
                    await send_message(
                        chat_id=admin_id,
                        text=admin_text,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=refund_buttons.build_menu(b_cols=1)
                    )
                except Exception as e:
                    logger.error(f"❌ Failed to notify admin {admin_id}: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Payment processing failed for user {user_id if user_id else 'unknown'}: {str(e)}")
            if chat_id:
                support_buttons = SmartButtons()
                support_buttons.button("📞 Contact Support", user_id=DEVELOPER_USER_ID)
                await send_message(
                    chat_id=chat_id,
                    text=PAYMENT_FAILED_TEXT,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=support_buttons.build_menu(b_cols=1)
                )