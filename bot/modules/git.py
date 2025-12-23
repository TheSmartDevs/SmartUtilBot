# Copyright @ISmartCoder
#  SmartUtilBot - Telegram Utility Bot for Smart Features Bot 
import os
import aiohttp
import aiofiles
import asyncio
from aiogram import Bot
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest
from bot import dp
from bot.helpers.utils import new_task, clean_download
from bot.helpers.botutils import send_message, delete_messages, get_args
from bot.helpers.commands import BotCommands
from bot.helpers.logger import LOGGER
from bot.helpers.notify import Smart_Notify
from bot.helpers.defend import SmartDefender

async def fetch_github_api(session: aiohttp.ClientSession, url: str):
    try:
        async with session.get(url) as response:
            response.raise_for_status()
            LOGGER.info(f"Successfully fetched data from '{url}'")
            return await response.json()
    except aiohttp.ClientError as e:
        LOGGER.error(f"GitHub API request failed for '{url}': {str(e)}")
        return None

async def get_repo_branches(session: aiohttp.ClientSession, repo_url: str):
    try:
        parts = repo_url.rstrip('/').split('/')
        user_name = parts[-2]
        repo_name = parts[-1].replace('.git', '')
        api_url = f"https://api.github.com/repos/{user_name}/{repo_name}/branches"
        LOGGER.info(f"Fetching branches for '{repo_url}' from '{api_url}'")
        branches_data = await fetch_github_api(session, api_url)
        if not branches_data:
            LOGGER.error(f"No branches data received for '{repo_url}'")
            raise Exception("Failed to fetch branches")
        return [branch['name'] for branch in branches_data]
    except Exception as e:
        LOGGER.error(f"Error fetching branches for '{repo_url}': {str(e)}")
        return None

async def get_github_repo_details(session: aiohttp.ClientSession, repo_url: str):
    try:
        parts = repo_url.rstrip('/').split('/')
        user_name = parts[-2]
        repo_name = parts[-1].replace('.git', '')
        api_url = f"https://api.github.com/repos/{user_name}/{repo_name}"
        LOGGER.info(f"Fetching repo details for '{repo_url}' from '{api_url}'")
        repo_data = await fetch_github_api(session, api_url)
        if not repo_data:
            LOGGER.error(f"No repo data received for '{repo_url}'")
            raise Exception("Failed to fetch repo details")
        return {
            'forks_count': repo_data.get('forks_count', 0),
            'description': repo_data.get('description', 'No description available'),
            'default_branch': repo_data.get('default_branch', 'main')
        }
    except Exception as e:
        LOGGER.error(f"Error fetching repo details for '{repo_url}': {str(e)}")
        return None

async def download_repo_zip(session: aiohttp.ClientSession, repo_url: str, branch: str, clone_dir: str):
    try:
        parts = repo_url.rstrip('/').split('/')
        user_name = parts[-2]
        repo_name = parts[-1].replace('.git', '')
        zip_url = f"https://api.github.com/repos/{user_name}/{repo_name}/zipball/{branch}"
        LOGGER.info(f"Downloading zip for '{repo_url}' branch '{branch}' from '{zip_url}'")
        async with session.get(zip_url) as response:
            response.raise_for_status()
            zip_path = f"{clone_dir}.zip"
            os.makedirs(os.path.dirname(zip_path), exist_ok=True)
            async with aiofiles.open(zip_path, 'wb') as f:
                while True:
                    chunk = await response.content.read(8192)
                    if not chunk:
                        break
                    await f.write(chunk)
            LOGGER.info(f"Successfully downloaded zip to '{zip_path}'")
            return zip_path
    except Exception as e:
        LOGGER.error(f"Error downloading zip for '{repo_url}' branch '{branch}': {str(e)}")
        return None

async def normalize_url(repo_url: str):
    repo_url = repo_url.strip()
    LOGGER.info(f"Normalizing URL: '{repo_url}'")
    if not repo_url.startswith(('http://', 'https://')):
        repo_url = f"https://{repo_url}"
    if not repo_url.endswith('.git'):
        repo_url = f"{repo_url.rstrip('/')}.git"
    LOGGER.info(f"Normalized URL: '{repo_url}'")
    return repo_url

@dp.message(Command(commands=["git"], prefix=BotCommands))
@new_task
@SmartDefender
async def git_download_handler(message: Message, bot: Bot):
    user_id = message.from_user.id if message.from_user else 'Unknown'
    chat_id = message.chat.id
    LOGGER.info(f"Received /git command from user: {user_id}")
    status_message = None
    try:
        args = get_args(message)
        if not args:
            status_message = await send_message(
                chat_id=chat_id,
                text="<b>Provide a valid GitHub repository URL.</b>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            LOGGER.error(f"No repository URL provided by user: {user_id}")
            return

        repo_url = await normalize_url(args[0])
        requested_branch = args[1] if len(args) > 1 else None

        parts = repo_url.rstrip('/').split('/')
        if len(parts) < 5 or parts[2] != "github.com":
            status_message = await send_message(
                chat_id=chat_id,
                text="<b>Provide a valid GitHub repository URL.</b>",
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=True
            )
            LOGGER.error(f"Invalid GitHub URL format: '{repo_url}'")
            return

        status_message = await send_message(
            chat_id=chat_id,
            text="<b>Downloading repository, please wait...</b>",
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True
        )

        async with aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=50),
            timeout=aiohttp.ClientTimeout(total=30)
        ) as session:
            user_name = parts[-2]
            repo_name = parts[-1].replace('.git', '')
            LOGGER.info(f"Processing repo: '{user_name}/{repo_name}'")

            repo_details_task = get_github_repo_details(session, repo_url)
            branches_task = get_repo_branches(session, repo_url)
            repo_details, branches = await asyncio.gather(repo_details_task, branches_task)

            if not branches or not repo_details:
                LOGGER.error(f"Failed to fetch repo details or branches for '{repo_url}'")
                raise Exception("Repository is private or inaccessible")

            forks_count = repo_details['forks_count']
            description = repo_details['description']

            if requested_branch:
                if requested_branch not in branches:
                    LOGGER.error(f"Branch '{requested_branch}' not found in '{repo_url}'. Available branches: {branches}")
                    raise Exception(f"Branch '{requested_branch}' not found")
                branch = requested_branch
            else:
                branch = "main" if "main" in branches else "master" if "master" in branches else branches[0]
            LOGGER.info(f"Selected branch: '{branch}'")

            clone_dir = f"./downloads/{repo_name}_{branch}"
            zip_path = await download_repo_zip(session, repo_url, branch, clone_dir)
            if not zip_path:
                LOGGER.error(f"Failed to download zip for '{repo_url}' branch '{branch}'")
                raise Exception("Failed to download repository zip")

            repo_info = (
                "<b>📁 Repository Details</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>Owner:</b> <code>{user_name}</code>\n"
                f"📂 <b>Name:</b> <code>{repo_name}</code>\n"
                f"🔀 <b>Forks:</b> <code>{forks_count}</code>\n"
                f"🌿 <b>Branch:</b> <code>{branch}</code>\n"
                f"🔗 <b>URL:</b> <code>{repo_url}</code>\n"
                "━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📝 <b>Description:</b>\n<code>{description}</code>\n\n"
                f"🌱 <b>Branches:</b> <code>{', '.join(branches)}</code>"
            )

            await delete_messages(chat_id, [status_message.message_id])
            await bot.send_document(
                chat_id=chat_id,
                document=FSInputFile(path=zip_path),
                caption=repo_info,
                parse_mode=ParseMode.HTML
            )
            LOGGER.info(f"Successfully sent zip file for '{repo_url}' branch '{branch}' to chat {chat_id}")

    except Exception as e:
        LOGGER.error(f"Error downloading repo '{repo_url}': {str(e)}")
        error_text = "<b>Provide a valid GitHub repository URL.</b>"
        if status_message:
            try:
                await status_message.edit_text(
                    text=error_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
                LOGGER.info(f"Edited status message with error in chat {chat_id}")
            except TelegramBadRequest as edit_e:
                LOGGER.error(f"Failed to edit status message in chat {chat_id}: {str(edit_e)}")
                await Smart_Notify(bot, "/git", edit_e, message)
                await send_message(
                    chat_id=chat_id,
                    text=error_text,
                    parse_mode=ParseMode.HTML
                )
        else:
            await send_message(
                chat_id=chat_id,
                text=error_text,
                parse_mode=ParseMode.HTML
            )
        LOGGER.info(f"Sent error message to chat {chat_id}")
    finally:
        if 'zip_path' in locals() and os.path.exists(zip_path):
            clean_download(zip_path)
            LOGGER.info(f"Cleaned up zip file: '{zip_path}'")