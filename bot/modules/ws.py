# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
#  Copyright (C) 2024-present Abir Arafat Chawdhury <https://github.com/abirxdhack> 
import os
import re
import asyncio
import zipfile
import tempfile
import aiohttp
import aiofiles
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.enums import ParseMode, ChatType
from bot import dp, SmartAIO
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages
from bot.helpers.logger import LOGGER
from bot.helpers.buttons import SmartButtons
from bot.helpers.commands import BotCommands
from bot.helpers.defend import SmartDefender

logger = LOGGER

class UrlDownloader:
    def __init__(self, imgFlg=True, linkFlg=True, scriptFlg=True):
        self.soup = None
        self.imgFlg = imgFlg
        self.linkFlg = linkFlg
        self.scriptFlg = scriptFlg
        self.linkType = ('css', 'png', 'ico', 'jpg', 'jpeg', 'mov', 'ogg', 'gif', 'xml', 'js')
        self.size_limit = 10 * 1024 * 1024
        self.semaphore = asyncio.Semaphore(50)

    async def savePage(self, url, pagefolder='page', session=None):
        try:
            async with session.get(url, timeout=10) as response:
                if response.status != 200:
                    return False, f"HTTP error {response.status}: {response.reason}", []
                
                content = await response.read()
                if len(content) > self.size_limit:
                    return False, "Size limit of 10 MB exceeded.", []
                
                if len(content) == 0:
                    return False, "Empty content received from URL.", []
                
                content_type = response.headers.get('content-type', '').lower()
                if not any(ct in content_type for ct in ['text/html', 'application/xhtml', 'text/xml']):
                    return False, f"Invalid content type: {content_type}. Expected HTML content.", []
                
                try:
                    self.soup = BeautifulSoup(content, features="lxml")
                except Exception as e:
                    try:
                        self.soup = BeautifulSoup(content, features="html.parser")
                    except Exception as e2:
                        return False, f"Failed to parse HTML content: {str(e2)}", []
                
                if self.soup is None:
                    return False, "Failed to parse HTML content.", []
                
                html_tag = self.soup.find('html')
                if html_tag is None:
                    if len(str(self.soup).strip()) == 0:
                        return False, "Invalid or empty HTML content.", []

            if not os.path.exists(pagefolder):
                os.makedirs(pagefolder, exist_ok=True)
            
            file_paths = []
            
            try:
                if self.imgFlg:
                    img_files = await self._soupfindnSave(url, pagefolder, tag2find='img', inner='src', session=session)
                    file_paths.extend(img_files)
                if self.linkFlg:
                    link_files = await self._soupfindnSave(url, pagefolder, tag2find='link', inner='href', session=session)
                    file_paths.extend(link_files)
                if self.scriptFlg:
                    script_files = await self._soupfindnSave(url, pagefolder, tag2find='script', inner='src', session=session)
                    file_paths.extend(script_files)
            except Exception as e:
                return False, f"Error during resource extraction: {str(e)}", file_paths
            
            html_path = os.path.join(pagefolder, 'page.html')
            
            try:
                html_content = self.soup.prettify('utf-8')
                async with aiofiles.open(html_path, 'wb') as file:
                    await file.write(html_content)
                file_paths.append(html_path)
            except Exception as e:
                return False, f"Failed to save HTML file: {str(e)}", file_paths
            
            return True, None, file_paths
            
        except asyncio.TimeoutError:
            return False, "Request timed out. Please try again.", []
        except aiohttp.ClientError as e:
            return False, f"Network error: {str(e)}", []
        except Exception as e:
            return False, f"Failed to download: {str(e)}", []

    async def _soupfindnSave(self, url, pagefolder, tag2find='img', inner='src', session=None):
        if self.soup is None:
            return []
        
        pagefolder = os.path.join(pagefolder, tag2find)
        if not os.path.exists(pagefolder):
            os.makedirs(pagefolder, exist_ok=True)
        
        tasks = []
        file_paths = []
        
        try:
            elements = self.soup.findAll(tag2find)
            if not elements:
                return []
        except Exception as e:
            return []
        
        for res in elements:
            try:
                if not res.has_attr(inner):
                    continue
                
                resource_url = res.get(inner)
                if not resource_url:
                    continue
                
                resource_url = resource_url.strip()
                if not resource_url or resource_url.startswith('data:'):
                    continue
                
                filename = re.sub(r'[^\w\-_\.]', '_', os.path.basename(resource_url))
                if not filename or filename == '_':
                    filename = f"resource_{len(file_paths)}"
                
                if tag2find == 'link' and not any(ext in filename.lower() for ext in self.linkType):
                    filename += '.html'
                
                fileurl = urljoin(url, resource_url)
                filepath = os.path.join(pagefolder, filename)
                file_paths.append(filepath)
                
                res[inner] = os.path.join(os.path.basename(pagefolder), filename)
                tasks.append(self._download_file(fileurl, filepath, session))
                
            except Exception as e:
                continue
        
        if tasks:
            try:
                for i in range(0, len(tasks), 50):
                    batch_tasks = tasks[i:i+50]
                    await asyncio.gather(*batch_tasks, return_exceptions=True)
            except Exception as e:
                pass
        
        return file_paths

    async def _download_file(self, fileurl, filepath, session):
        async with self.semaphore:
            try:
                async with session.get(fileurl, timeout=5) as response:
                    if response.status != 200:
                        return
                    
                    content = await response.read()
                    if len(content) > self.size_limit or len(content) == 0:
                        return
                    
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    async with aiofiles.open(filepath, 'wb') as file:
                        await file.write(content)
            except asyncio.TimeoutError:
                pass
            except Exception as exc:
                pass

def create_zip(folder_path):
    try:
        if not os.path.exists(folder_path):
            return None
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        temp_file.close()
        
        with zipfile.ZipFile(temp_file.name, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            file_count = 0
            for root, _, files in os.walk(folder_path):
                for file in files:
                    try:
                        file_path = os.path.join(root, file)
                        if os.path.exists(file_path):
                            zip_file.write(file_path, os.path.relpath(file_path, folder_path))
                            file_count += 1
                    except Exception as e:
                        pass
            
            if file_count == 0:
                os.unlink(temp_file.name)
                return None
                
        return temp_file.name
    except Exception as e:
        return None

async def notify_admin(bot: Bot, command: str, exception: Exception, message: Message):
    pass

@dp.message(Command(commands=["ws", "websource"], prefix=BotCommands))
@new_task
@SmartDefender
async def websource(message: Message, bot: Bot):
    if message.chat.type not in [ChatType.PRIVATE, ChatType.GROUP, ChatType.SUPERGROUP]:
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ This command only works in private or group chats</b>",
            parse_mode=ParseMode.HTML
        )
        return
    
    if len(message.text.split()) < 2:
        await send_message(
            chat_id=message.chat.id,
            text="<b>❌ Please provide at least one valid URL.</b>",
            parse_mode=ParseMode.HTML
        )
        return
    
    url = message.text.split()[1]
    if not url.startswith(('http://', 'https://')):
        url = f"https://{url}"
    
    loading_message = await send_message(
        chat_id=message.chat.id,
        text="<b>Downloading Website Source...</b>",
        parse_mode=ParseMode.HTML
    )
    
    pagefolder = os.path.join("downloads", f"page_{message.chat.id}_{message.message_id}")
    zip_file_path = None
    
    try:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        ) as session:
            downloader = UrlDownloader()
            success, error, file_paths = await downloader.savePage(url, pagefolder, session)
            
            if not success:
                await SmartAIO.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=loading_message.message_id,
                    text=f"<b>❌ Failed to download source code.</b>\n<code>{error}</code>",
                    parse_mode=ParseMode.HTML
                )
                await notify_admin(bot, "/ws", Exception(error), message)
                if file_paths:
                    clean_download(*file_paths)
                return
            
            zip_file_path = create_zip(pagefolder)
            if zip_file_path is None:
                await SmartAIO.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=loading_message.message_id,
                    text="<b>❌ Failed to create zip file. No files were downloaded.</b>",
                    parse_mode=ParseMode.HTML
                )
                clean_download(*file_paths)
                return
            
            user = message.from_user
            user_mention = f"<a href=\"tg://user?id={user.id}\">{user.first_name} {user.last_name or ''}</a>".strip()
            caption = (
                "<b>Source Code Downloaded ✅</b>\n"
                "<b>━━━━━━━━━━━</b>\n"
                f"<b>Site:</b> <code>{url}</code>\n"
                f"<b>Files:</b> <b>HTML, CSS, JS</b>\n"
                "<b>━━━━━━━━━━━</b>\n"
                f"<b>Downloaded By:</b> {user_mention}"
            )
            
            await delete_messages(chat_id=message.chat.id, message_ids=loading_message.message_id)
            
            await SmartAIO.send_document(
                chat_id=message.chat.id,
                document=FSInputFile(zip_file_path, filename=f"{urlparse(url).netloc}_source.zip"),
                caption=caption,
                parse_mode=ParseMode.HTML
            )
            
            clean_download(*file_paths)
            
    except Exception as e:
        try:
            await SmartAIO.edit_message_text(
                chat_id=message.chat.id,
                message_id=loading_message.message_id,
                text="<b>❌ An unexpected error occurred. Please try again later.</b>",
                parse_mode=ParseMode.HTML
            )
        except:
            pass
        await notify_admin(bot, "/ws", e, message)
        if 'file_paths' in locals():
            clean_download(*file_paths)
    finally:
        if zip_file_path and os.path.exists(zip_file_path):
            try:
                os.unlink(zip_file_path)
            except Exception as e:
                pass