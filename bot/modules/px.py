# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
#  Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
import asyncio
import socket
import aiohttp
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode, ChatType
from bot import dp, SmartAIO
from bot.helpers.utils import new_task
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.notify import Smart_Notify
from bot.helpers.logger import LOGGER
from bot.helpers.commands import BotCommands
from bot.helpers.defend import SmartDefender
from config import IPINFO_API_TOKEN, PROXY_CHECK_LIMIT

logger = LOGGER
PROXY_TIMEOUT = 10
GEOLOCATION_TIMEOUT = 3

class HTTPProxyChecker:
    def __init__(self):
        self.geo_service = {
            'name': 'ipinfo.io',
            'url': "https://ipinfo.io/{ip}/json",
            'parser': lambda data: f"{data.get('region', 'Unknown')} ({data.get('country', 'Unknown')})",
            'headers': {'User-Agent': 'Mozilla/5.0', 'Authorization': f'Bearer {IPINFO_API_TOKEN}'}
        }

    async def get_location(self, session, ip):
        try:
            url = self.geo_service['url'].format(ip=ip)
            async with session.get(
                url,
                headers=self.geo_service.get('headers', {}),
                timeout=GEOLOCATION_TIMEOUT
            ) as response:
                data = await response.json()
                logger.info(f"Location API Response: {data}")
                if response.status == 200:
                    return self.geo_service['parser'](data)
                return f"❌ HTTP {response.status}"
        except asyncio.TimeoutError:
            return "⏳ Timeout"
        except Exception as e:
            logger.error(f"Error fetching location: {e}")
            return f"❌ Error ({str(e)[:30]})"

    async def check_proxy(self, proxy, proxy_type='http', auth=None):
        result = {
            'proxy': f"{proxy}",
            'status': 'Dead 🔴',
            'location': '• Not determined'
        }
        ip, port = proxy.split(':')[:2]
        port = int(port)
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(PROXY_TIMEOUT)
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: sock.connect((ip, port))
            )
            sock.close()
            result['status'] = 'Live ✅'
            result['ip'] = ip
            async with aiohttp.ClientSession() as session:
                result['location'] = await self.get_location(session, ip)
        except Exception as e:
            logger.error(f"Error checking proxy {proxy}: {e}")
            async with aiohttp.ClientSession() as session:
                result['location'] = await self.get_location(session, ip)
        return result

checker = HTTPProxyChecker()

@dp.message(Command(commands=["px", "proxy"], prefix=BotCommands))
@new_task
@SmartDefender
async def px_command_handler(message: Message, bot: Bot):
    if message.chat.type not in [ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP]:
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ This command only works in private or group chats</b>",
            parse_mode=ParseMode.HTML
        )
        return
    user_id = message.from_user.id
    logger.info(f"Command received from user {user_id} in chat {message.chat.id}: {message.text}")
    args = get_args(message)
    proxies_to_check = []
    auth = None
    if args:
        if len(args) == 1 and args[0].count(':') == 3:
            ip_port, username, password = args[0].rsplit(':', 2)
            proxies_to_check.append(('http', ip_port))
            auth = {'username': username, 'password': password}
        elif len(args) >= 3 and ':' not in args[-1] and ':' not in args[-2]:
            auth = {'username': args[-2], 'password': args[-1]}
            proxy_args = args[:-2]
            for proxy in proxy_args:
                if '://' in proxy:
                    parts = proxy.split('://')
                    if len(parts) == 2 and parts[0].lower() in ['http', 'https']:
                        proxies_to_check.append((parts[0].lower(), parts[1]))
                elif ':' in proxy:
                    proxies_to_check.append(('http', proxy))
        else:
            for proxy in args:
                if '://' in proxy:
                    parts = proxy.split('://')
                    if len(parts) == 2 and parts[0].lower() in ['http', 'https']:
                        proxies_to_check.append((parts[0].lower(), parts[1]))
                elif ':' in proxy:
                    proxies_to_check.append(('http', proxy))
    else:
        if message.reply_to_message and message.reply_to_message.text:
            proxy_text = message.reply_to_message.text
            potential_proxies = proxy_text.split()
            for proxy in potential_proxies:
                if ':' in proxy:
                    if proxy.count(':') == 3:
                        ip_port, username, password = proxy.rsplit(':', 2)
                        proxies_to_check.append(('http', ip_port))
                        auth = {'username': username, 'password': password}
                    else:
                        proxies_to_check.append(('http', proxy))
        else:
            await send_message(
                chat_id=message.chat.id,
                text="<b>❌ Provide at least one proxy for check</b>",
                parse_mode=ParseMode.HTML
            )
            return
    if not proxies_to_check:
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ The Proxies Are Not Valid At All</b>",
            parse_mode=ParseMode.HTML
        )
        return
    if len(proxies_to_check) > PROXY_CHECK_LIMIT:
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Sorry Bro Maximum Proxy Check Limit Is 20</b>",
            parse_mode=ParseMode.HTML
        )
        return
    processing_msg = await send_message(
        chat_id=message.chat.id,
        text="<b>Smart Proxy Checker Checking Proxies 💥</b>",
        parse_mode=ParseMode.HTML
    )
    try:
        tasks = [checker.check_proxy(proxy, proxy_type, auth) for proxy_type, proxy in proxies_to_check]
        results = await asyncio.gather(*tasks)
        response = []
        for res in results:
            response.append(f"<b>Proxy:</b> <code>{res['proxy']}</code>\n")
            response.append(f"<b>Status:</b> {res['status']}\n")
            response.append(f"<b>Region:</b> {res['location']}\n")
            response.append("\n")
        full_response = ''.join(response)
        try:
            await processing_msg.edit_text(
                text=full_response,
                parse_mode=ParseMode.HTML
            )
        except Exception:
            await delete_messages(
                chat_id=message.chat.id,
                message_ids=[processing_msg.message_id]
            )
            await send_message(
                chat_id=message.chat.id,
                text=full_response,
                parse_mode=ParseMode.HTML
            )
    except Exception as e:
        logger.error(f"Error during proxy check: {e}")
        await Smart_Notify(bot, "/px", e, message)
        try:
            await processing_msg.edit_text(
                text="<b>Sorry Bro Proxy Checker API Dead</b>",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            await delete_messages(
                chat_id=message.chat.id,
                message_ids=[processing_msg.message_id]
            )
            await send_message(
                chat_id=message.chat.id,
                text="<b>Sorry Bro Proxy Checker API Dead</b>",
                parse_mode=ParseMode.HTML
            )