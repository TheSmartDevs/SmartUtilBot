import os
import re
import asyncio
import zipfile
import tempfile
import aiohttp
import aiofiles
import html
from urllib.parse import urljoin, urlparse, unquote
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
from bot.helpers.notify import Smart_Notify

logger = LOGGER

class UrlDownloader:
    def __init__(self, imgFlg=True, linkFlg=True, scriptFlg=True):
        self.soup = None
        self.imgFlg = imgFlg
        self.linkFlg = linkFlg
        self.scriptFlg = scriptFlg
        self.extensions = {
            'css': 'css',
            'js': 'js',
            'mjs': 'js',
            'png': 'images',
            'jpg': 'images',
            'jpeg': 'images',
            'gif': 'images',
            'svg': 'images',
            'ico': 'images',
            'webp': 'images',
            'avif': 'images',
            'woff': 'fonts',
            'woff2': 'fonts',
            'ttf': 'fonts',
            'eot': 'fonts',
            'otf': 'fonts',
            'json': 'json',
            'xml': 'xml',
            'txt': 'txt',
            'pdf': 'documents',
            'mov': 'media',
            'mp4': 'media',
            'webm': 'media',
            'ogg': 'media',
            'mp3': 'media'
        }
        self.size_limit = 19 * 1024 * 1024
        self.semaphore = asyncio.Semaphore(25)
        self.downloaded_files = set()
        self.failed_urls = set()

    async def savePage(self, url, pagefolder='page', session=None):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'identity',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none'
            }

            async with session.get(url, timeout=20, headers=headers, allow_redirects=True) as response:
                if response.status != 200:
                    return False, f"HTTP error {response.status}: {response.reason}", []

                content = await response.read()
                if len(content) > self.size_limit:
                    return False, "Size limit of 19 MB exceeded.", []

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

            if not os.path.exists(pagefolder):
                os.makedirs(pagefolder, exist_ok=True)

            file_paths = []
            all_resource_urls = set()

            if self.linkFlg:
                css_urls = self._extract_css_resources(url)
                all_resource_urls.update(css_urls)

            if self.scriptFlg:
                js_urls = self._extract_js_resources(url)
                all_resource_urls.update(js_urls)

            if self.imgFlg:
                img_urls = self._extract_image_resources(url)
                all_resource_urls.update(img_urls)

            other_urls = self._extract_other_resources(url)
            all_resource_urls.update(other_urls)

            inline_urls = self._extract_inline_urls(str(self.soup), url)
            all_resource_urls.update(inline_urls)

            meta_urls = self._extract_meta_resources(url)
            all_resource_urls.update(meta_urls)

            all_resource_urls = [u for u in all_resource_urls if u and self._is_valid_url(u)]

            if all_resource_urls:
                downloaded_resources = await self._download_all_resources(list(all_resource_urls), pagefolder, session)
                file_paths.extend(downloaded_resources)

            await self._update_html_paths(url, pagefolder)

            html_path = os.path.join(pagefolder, 'index.html')
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

    def _is_valid_url(self, url):
        if not url or not isinstance(url, str):
            return False
        return not url.startswith(('data:', 'blob:', 'javascript:', 'mailto:', 'tel:', '#', 'about:'))

    def _extract_css_resources(self, base_url):
        urls = set()
        if self.soup is None:
            return urls

        for link in self.soup.find_all('link', href=True):
            rel = link.get('rel', [])
            if isinstance(rel, str):
                rel = [rel]

            if 'stylesheet' in rel or link.get('type') == 'text/css':
                href = link.get('href')
                if href:
                    full_url = urljoin(base_url, href.strip())
                    urls.add(full_url)

        for style in self.soup.find_all('style'):
            if style.string:
                style_urls = self._extract_css_urls(style.string, base_url)
                urls.update(style_urls)

        return urls

    def _extract_js_resources(self, base_url):
        urls = set()
        if self.soup is None:
            return urls

        for script in self.soup.find_all('script', src=True):
            src = script.get('src')
            if src:
                full_url = urljoin(base_url, src.strip())
                urls.add(full_url)

        return urls

    def _extract_image_resources(self, base_url):
        urls = set()
        if self.soup is None:
            return urls

        for img in self.soup.find_all('img'):
            if img.get('src'):
                src_url = urljoin(base_url, img.get('src').strip())
                urls.add(src_url)

            if img.get('data-src'):
                lazy_url = urljoin(base_url, img.get('data-src').strip())
                urls.add(lazy_url)

            if img.get('srcset'):
                srcset_urls = self._parse_srcset(img.get('srcset'), base_url)
                urls.update(srcset_urls)

        for source in self.soup.find_all('source'):
            if source.get('src'):
                src_url = urljoin(base_url, source.get('src').strip())
                urls.add(src_url)
            if source.get('srcset'):
                srcset_urls = self._parse_srcset(source.get('srcset'), base_url)
                urls.update(srcset_urls)

        return urls

    def _extract_other_resources(self, base_url):
        urls = set()
        if self.soup is None:
            return urls

        for link in self.soup.find_all('link', href=True):
            rel = link.get('rel', [])
            if isinstance(rel, str):
                rel = [rel]

            if any(r in rel for r in ['icon', 'shortcut icon', 'apple-touch-icon', 'manifest', 'alternate', 'canonical', 'preload', 'prefetch', 'dns-prefetch']):
                href = link.get('href')
                if href and not href.startswith(('http://', 'https://')) or href.startswith('/'):
                    full_url = urljoin(base_url, href.strip())
                    urls.add(full_url)
                elif href and href.startswith(('http://', 'https://')):
                    urls.add(href.strip())

        for audio in self.soup.find_all('audio', src=True):
            src_url = urljoin(base_url, audio.get('src').strip())
            urls.add(src_url)

        for video in self.soup.find_all('video', src=True):
            src_url = urljoin(base_url, video.get('src').strip())
            urls.add(src_url)

        for embed in self.soup.find_all('embed', src=True):
            src_url = urljoin(base_url, embed.get('src').strip())
            urls.add(src_url)

        for obj in self.soup.find_all('object', data=True):
            data_url = urljoin(base_url, obj.get('data').strip())
            urls.add(data_url)

        return urls

    def _extract_meta_resources(self, base_url):
        urls = set()
        if self.soup is None:
            return urls

        for meta in self.soup.find_all('meta'):
            content = meta.get('content', '')
            if content and (content.startswith(('http://', 'https://', '/')) or '.' in content):
                if content.startswith('/'):
                    meta_url = urljoin(base_url, content)
                    urls.add(meta_url)
                elif content.startswith(('http://', 'https://')):
                    urls.add(content)

        return urls

    def _parse_srcset(self, srcset, base_url):
        urls = set()
        if not srcset:
            return urls

        entries = srcset.split(',')
        for entry in entries:
            entry = entry.strip()
            if entry:
                parts = entry.split()
                if parts:
                    url_part = parts[0].strip()
                    if url_part:
                        full_url = urljoin(base_url, url_part)
                        urls.add(full_url)
        return urls

    def _extract_css_urls(self, css_content, base_url):
        urls = set()

        url_pattern = r'url\s*\(\s*["\']?([^"\'()]+)["\']?\s*\)'
        css_urls = re.findall(url_pattern, css_content, re.IGNORECASE)
        for css_url in css_urls:
            if not css_url.startswith(('data:', 'blob:', 'javascript:')):
                full_url = urljoin(base_url, css_url.strip())
                urls.add(full_url)

        import_pattern = r'@import\s+["\']([^"\']+)["\']'
        import_urls = re.findall(import_pattern, css_content, re.IGNORECASE)
        for import_url in import_urls:
            full_url = urljoin(base_url, import_url.strip())
            urls.add(full_url)

        return urls

    def _extract_inline_urls(self, html_content, base_url):
        urls = set()

        style_blocks = re.findall(r'<style[^>]*>(.*?)</style>', html_content, re.DOTALL | re.IGNORECASE)
        for style_block in style_blocks:
            style_urls = self._extract_css_urls(style_block, base_url)
            urls.update(style_urls)

        script_blocks = re.findall(r'<script[^>]*>(.*?)</script>', html_content, re.DOTALL | re.IGNORECASE)
        for script_block in script_blocks:
            js_urls = re.findall(r'["\']([^"\']*\.(js|css|png|jpg|jpeg|gif|svg|woff2?|ttf|eot|json|xml))["\']', script_block, re.IGNORECASE)
            for js_url_match in js_urls:
                js_url = js_url_match[0]
                if js_url and not js_url.startswith(('data:', 'blob:', 'javascript:')):
                    full_url = urljoin(base_url, js_url.strip())
                    urls.add(full_url)

        return urls

    async def _download_all_resources(self, resource_urls, pagefolder, session):
        tasks = []
        file_paths = []

        for resource_url in resource_urls:
            if resource_url not in self.downloaded_files and resource_url not in self.failed_urls:
                self.downloaded_files.add(resource_url)
                file_path = self._get_resource_path(resource_url, pagefolder)
                if file_path:
                    file_paths.append(file_path)
                    tasks.append(self._download_single_resource(resource_url, file_path, session))

        if tasks:
            try:
                batch_size = 25
                for i in range(0, len(tasks), batch_size):
                    batch_tasks = tasks[i:i+batch_size]
                    results = await asyncio.gather(*batch_tasks, return_exceptions=True)
                    await asyncio.sleep(0.2)
            except Exception as e:
                pass

        return file_paths

    def _get_resource_path(self, resource_url, pagefolder):
        try:
            parsed_url = urlparse(resource_url)
            path = unquote(parsed_url.path)

            if not path or path == '/':
                query = parsed_url.query
                fragment = parsed_url.fragment
                if query:
                    path = f"/query_{abs(hash(query)) % 100000}"
                elif fragment:
                    path = f"/fragment_{abs(hash(fragment)) % 100000}"
                else:
                    path = f"/resource_{abs(hash(resource_url)) % 100000}"

            path_parts = path.strip('/').split('/') if path.strip('/') else ['index']
            filename = path_parts[-1] if path_parts[-1] else 'index'

            if '.' in filename and len(filename.split('.')[-1]) <= 10:
                file_ext = filename.split('.')[-1].lower()
            else:
                file_ext = self._guess_extension_from_url(resource_url)
                if file_ext:
                    filename = f"{filename}.{file_ext}"
                else:
                    filename = f"{filename}.html"
                file_ext = file_ext or 'html'

            folder_name = self.extensions.get(file_ext, 'assets')

            if len(path_parts) > 1:
                subfolder_path = '/'.join(path_parts[:-1])
                target_folder = os.path.join(pagefolder, folder_name, subfolder_path)
            else:
                target_folder = os.path.join(pagefolder, folder_name)

            os.makedirs(target_folder, exist_ok=True)

            counter = 1
            base_filename = filename
            while True:
                full_path = os.path.join(target_folder, filename)
                if not os.path.exists(full_path):
                    break
                name, ext = os.path.splitext(base_filename)
                filename = f"{name}_{counter}{ext}"
                counter += 1

            return full_path

        except Exception as e:
            return None

    def _guess_extension_from_url(self, url):
        url_lower = url.lower()

        if any(keyword in url_lower for keyword in ['css', 'style']):
            return 'css'
        elif any(keyword in url_lower for keyword in ['js', 'javascript', 'script']):
            return 'js'
        elif any(ext in url_lower for ext in ['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'ico', 'avif']):
            for ext in ['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'ico', 'avif']:
                if ext in url_lower:
                    return ext
        elif any(ext in url_lower for ext in ['woff2', 'woff', 'ttf', 'otf', 'eot']):
            for ext in ['woff2', 'woff', 'ttf', 'otf', 'eot']:
                if ext in url_lower:
                    return ext
        elif 'json' in url_lower or 'manifest' in url_lower:
            return 'json'
        elif 'xml' in url_lower:
            return 'xml'

        return None

    async def _download_single_resource(self, resource_url, file_path, session):
        async with self.semaphore:
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': '*/*',
                    'Accept-Encoding': 'identity',
                    'Cache-Control': 'no-cache',
                    'Referer': resource_url,
                    'Sec-Fetch-Dest': 'empty',
                    'Sec-Fetch-Mode': 'cors',
                    'Sec-Fetch-Site': 'cross-site'
                }

                async with session.get(resource_url, timeout=15, headers=headers, allow_redirects=True) as response:
                    if response.status not in [200, 206]:
                        self.failed_urls.add(resource_url)
                        return False

                    content = await response.read()
                    if len(content) > self.size_limit or len(content) == 0:
                        self.failed_urls.add(resource_url)
                        return False

                    os.makedirs(os.path.dirname(file_path), exist_ok=True)

                    if file_path.endswith('.css'):
                        try:
                            decoded_content = content.decode('utf-8', errors='ignore')
                            processed_content = await self._process_css_content(decoded_content, resource_url, session)
                            content = processed_content.encode('utf-8')
                        except:
                            pass

                    async with aiofiles.open(file_path, 'wb') as file:
                        await file.write(content)

                    return True

            except Exception as e:
                self.failed_urls.add(resource_url)
                return False

    async def _process_css_content(self, css_content, base_url, session):
        def replace_url(match):
            url = match.group(1).strip('\'"')
            if not url.startswith(('data:', 'http://', 'https://')):
                full_url = urljoin(base_url, url)
                return f'url("{full_url}")'
            return match.group(0)

        css_content = re.sub(r'url\s*\(\s*["\']?([^"\'()]+)["\']?\s*\)', replace_url, css_content)
        return css_content

    async def _update_html_paths(self, base_url, pagefolder):
        if self.soup is None:
            return

        for img_tag in self.soup.find_all('img'):
            if img_tag.get('src'):
                original_url = urljoin(base_url, img_tag.get('src'))
                local_path = self._get_local_path(original_url, pagefolder)
                if local_path:
                    img_tag['src'] = local_path

        for link_tag in self.soup.find_all('link'):
            if link_tag.get('href'):
                original_url = urljoin(base_url, link_tag.get('href'))
                local_path = self._get_local_path(original_url, pagefolder)
                if local_path:
                    link_tag['href'] = local_path

        for script_tag in self.soup.find_all('script'):
            if script_tag.get('src'):
                original_url = urljoin(base_url, script_tag.get('src'))
                local_path = self._get_local_path(original_url, pagefolder)
                if local_path:
                    script_tag['src'] = local_path

    def _get_local_path(self, resource_url, pagefolder):
        try:
            parsed_url = urlparse(resource_url)
            path = unquote(parsed_url.path)

            if not path or path == '/':
                return None

            path_parts = path.strip('/').split('/') if path.strip('/') else ['index']
            filename = path_parts[-1] if path_parts[-1] else 'index'

            if '.' in filename and len(filename.split('.')[-1]) <= 10:
                file_ext = filename.split('.')[-1].lower()
            else:
                file_ext = self._guess_extension_from_url(resource_url) or 'html'
                filename = f"{filename}.{file_ext}"

            folder_name = self.extensions.get(file_ext, 'assets')

            if len(path_parts) > 1:
                subfolder = '/'.join(path_parts[:-1])
                local_path = f"{folder_name}/{subfolder}/{filename}"
            else:
                local_path = f"{folder_name}/{filename}"

            return local_path
        except:
            return None

def create_zip(folder_path):
    try:
        if not os.path.exists(folder_path):
            return None

        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        temp_file.close()

        with zipfile.ZipFile(temp_file.name, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as zip_file:
            file_count = 0
            total_size = 0

            for root, _, files in os.walk(folder_path):
                for file in files:
                    try:
                        file_path = os.path.join(root, file)
                        if os.path.exists(file_path):
                            file_size = os.path.getsize(file_path)
                            if total_size + file_size > 19 * 1024 * 1024:
                                continue

                            arc_name = os.path.relpath(file_path, folder_path)
                            zip_file.write(file_path, arc_name)
                            file_count += 1
                            total_size += file_size
                    except Exception as e:
                        continue

            if file_count == 0:
                os.unlink(temp_file.name)
                return None

        return temp_file.name
    except Exception as e:
        return None

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
        text="<b>🔄 Downloading Website Source...</b>\n<i>Extracting HTML, CSS, JS, Images & Assets...</i>",
        parse_mode=ParseMode.HTML
    )

    pagefolder = os.path.join("downloads", f"page_{message.chat.id}_{message.message_id}")
    zip_file_path = None
    start_time = asyncio.get_event_loop().time()

    try:
        connector = aiohttp.TCPConnector(limit=150, limit_per_host=50, ttl_dns_cache=300, use_dns_cache=True)
        timeout = aiohttp.ClientTimeout(total=120, connect=20, sock_read=15)

        async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'},
            auto_decompress=False
        ) as session:
            downloader = UrlDownloader()
            success, error, file_paths = await downloader.savePage(url, pagefolder, session)

            if not success:
                await SmartAIO.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=loading_message.message_id,
                    text=f"<b>❌ Failed to download source code.</b>\n<code>{html.escape(error)}</code>",
                    parse_mode=ParseMode.HTML
                )
                await Smart_Notify(bot, "/ws", Exception(error), message)
                if file_paths:
                    clean_download(*file_paths)
                return

            await SmartAIO.edit_message_text(
                chat_id=message.chat.id,
                message_id=loading_message.message_id,
                text="<b>📦 Creating ZIP archive...</b>",
                parse_mode=ParseMode.HTML
            )

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

            zip_size = os.path.getsize(zip_file_path)
            zip_size_mb = zip_size / (1024 * 1024)
            file_count = len([f for f in file_paths if os.path.exists(f)])
            end_time = asyncio.get_event_loop().time()
            time_taken = end_time - start_time

            user = message.from_user
            first_name = html.escape(user.first_name)
            last_name = html.escape(user.last_name) if user.last_name else ''
            user_mention = f"<a href=\"tg://user?id={user.id}\">{first_name} {last_name}</a>".strip()
            domain = urlparse(url).netloc
            domain_clean = domain.replace('www.', '')

            caption = (
                "<b>Website Source Download Successful ➺ ✅</b>\n"
                "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>⊗ Website:</b> <code>{html.escape(domain)}</code>\n"
                f"<b>⊗ Total Files:</b> <code>{file_count}</code>\n"
                f"<b>⊗ Archive Size:</b> <code>{zip_size_mb:.2f} MB</code>\n"
                f"<b>⊗ File Contains:</b> <i>HTML, CSS, JS, Images, Fonts & Assets</i>\n"
                f"<b>⊗ Time Taken:</b> <code>{time_taken:.2f}s</code>\n"
                "<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                f"<b>Downloaded By:</b> {user_mention}"
            )

            await delete_messages(chat_id=message.chat.id, message_ids=loading_message.message_id)

            await SmartAIO.send_document(
                chat_id=message.chat.id,
                document=FSInputFile(zip_file_path, filename=f"SmartSourceCode({html.escape(domain_clean)}).zip"),
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
        await Smart_Notify(bot, "/ws", e, message)
        if 'file_paths' in locals():
            clean_download(*file_paths)
    finally:
        if zip_file_path and os.path.exists(zip_file_path):
            try:
                os.unlink(zip_file_path)
            except Exception as e:
                pass