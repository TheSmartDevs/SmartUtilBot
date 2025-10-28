import asyncio
import pycountry
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ParseMode
from bot import dp
from bot.helpers.utils import new_task
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.buttons import SmartButtons
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.defend import SmartDefender
from smartfaker import Faker

fake = Faker()

def get_flag(country_code):
    try:
        country = pycountry.countries.get(alpha_2=country_code)
        if not country:
            return "Unknown", ""
        name = country.name
        flag = chr(0x1F1E6 + ord(country_code[0]) - ord('A')) + chr(0x1F1E6 + ord(country_code[1]) - ord('A'))
        return name, flag
    except:
        return "Unknown", ""

def resolve_country(inp):
    inp = inp.strip().upper()
    maps = {
        "UK": ("GB", "United Kingdom"),
        "UAE": ("AE", "United Arab Emirates"),
        "AE": ("AE", "United Arab Emirates"),
        "UNITED KINGDOM": ("GB", "United Kingdom"),
        "UNITED ARAB EMIRATES": ("AE", "United Arab Emirates")
    }
    if inp in maps:
        return maps[inp]
    if len(inp) == 2:
        c = pycountry.countries.get(alpha_2=inp)
        if c:
            return c.alpha_2, c.name
    try:
        c = pycountry.countries.search_fuzzy(inp)[0]
        return c.alpha_2, c.name
    except:
        return None, None

async def fetch_fake_address(code):
    try:
        res = await fake.address(code, 1)
        if isinstance(res, dict) and "country" in res:
            return res
        LOGGER.error(f"Faker invalid response: {res}")
        return None
    except Exception as e:
        LOGGER.error(f"Faker error: {e}")
        return None

async def render_address(chat_id, code, user_id, bot, edit_msg=None):
    data = await fetch_fake_address(code)
    if not data:
        txt = "<b>Failed to generate address</b>"
        if edit_msg:
            await edit_msg.edit_text(txt, parse_mode=ParseMode.HTML)
        else:
            await send_message(chat_id, txt, ParseMode.HTML)
        return
    name, flag = get_flag(code)
    txt = (
        f"<b>Address for {name} {flag}</b>\n"
        f"<b>━━━━━━━━━━━━━</b>\n"
        f"<b>- Street :</b> <code>{data['building_number']} {data['street_name']}</code>\n"
        f"<b>- Street Name :</b> <code>{data['street_name']}</code>\n"
        f"<b>- Currency :</b> <code>{data['currency']}</code>\n"
        f"<b>- Full Name :</b> <code>{data['person_name']}</code>\n"
        f"<b>- City/Town/Village :</b> <code>{data['city']}</code>\n"
        f"<b>- Gender :</b> <code>{data['gender']}</code>\n"
        f"<b>- Postal Code :</b> <code>{data['postal_code']}</code>\n"
        f"<b>- Phone Number :</b> <code>{data['phone_number']}</code>\n"
        f"<b>- State :</b> <code>{data['state']}</code>\n"
        f"<b>- Country :</b> <code>{data['country']}</code>\n"
        f"<b>━━━━━━━━━━━━━</b>\n"
        f"<b>Click Below Button</b>"
    )
    btn = SmartButtons()
    cb = f"fake_regen|{code}|{user_id}"
    btn.button("Re-Generate", callback_data=cb)
    markup = btn.build_menu(b_cols=1)
    if edit_msg:
        await edit_msg.edit_text(txt, parse_mode=ParseMode.HTML, reply_markup=markup)
    else:
        await send_message(chat_id, txt, ParseMode.HTML, reply_markup=markup)

@dp.message(Command(commands=["fake", "rnd"], prefix=BotCommands))
@new_task
@SmartDefender
async def fake_cmd(message: Message, bot: Bot):
    LOGGER.info(f"fake command from {message.from_user.id} in {message.chat.id}")
    prog = None
    try:
        args = get_args(message)
        if not args:
            prog = await send_message(message.chat.id, "<b>Please provide country</b>", ParseMode.HTML)
            return
        code, _ = resolve_country(args[0])
        if not code or len(code) != 2:
            prog = await send_message(message.chat.id, "<b>Invalid country</b>", ParseMode.HTML)
            return
        prog = await send_message(message.chat.id, "<b>Generating address...</b>", ParseMode.HTML)
        uid = message.from_user.id if message.from_user else 0
        await delete_messages(message.chat.id, [prog.message_id])
        await render_address(message.chat.id, code, uid, bot)
    except Exception as e:
        LOGGER.error(f"fake_cmd error: {e}")
        await Smart_Notify(bot, "fake", e, message)
        if prog:
            await delete_messages(message.chat.id, [prog.message_id])
        await send_message(message.chat.id, "<b>Generation failed</b>", ParseMode.HTML)

@dp.callback_query(lambda c: c.data and c.data.startswith("fake_regen|"))
@new_task
async def fake_regen_cb(callback_query: CallbackQuery, bot: Bot):
    LOGGER.info(f"fake_regen callback {callback_query.data}")
    try:
        _, code, uid_str = callback_query.data.split("|", 2)
        uid = int(uid_str)
        if callback_query.from_user.id != uid:
            await callback_query.answer("This Is Not Your's Kid", show_alert=True)
            return
        await render_address(callback_query.message.chat.id, code, uid, bot, edit_msg=callback_query.message)
        await callback_query.answer()
    except Exception as e:
        LOGGER.error(f"fake_regen_cb error: {e}")
        await Smart_Notify(bot, "fake_regen", e, callback_query.message)
        await callback_query.answer("Regen failed", show_alert=True)