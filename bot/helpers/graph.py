from telegraph import Telegraph
from bot.helpers.logger import LOGGER
import asyncio

class SmartGraph:
    def __init__(self):
        self.telegraph = Telegraph()
        self.max_retries = 5
        self.retry_delay = 1
        self.initialized = False

    async def initialize(self):
        if self.initialized:
            return True

        LOGGER.info("Creating Telegraph Client From Telegraph")

        for attempt in range(self.max_retries):
            try:
                self.telegraph.create_account(
                    short_name="SmartUtilBot",
                    author_name="SmartUtilBot",
                    author_url="https://t.me/abirxdhackz"
                )
                LOGGER.info("Telegraph Client Created Successfully!")
                self.initialized = True
                return True
            except Exception as e:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue
                LOGGER.error("Failed To Create Telegraph Account!")
                self.initialized = False
                return False

    async def create_page(self, title, content, author_name="SmartUtilBot", author_url="https://t.me/abirxdhackz"):
        if not self.initialized:
            if not await self.initialize():
                return None

        for attempt in range(self.max_retries):
            try:
                safe_content = content.replace('<', '&lt;').replace('>', '&gt;')
                page = self.telegraph.create_page(
                    title=title,
                    html_content=f"<pre>{safe_content}</pre>",
                    author_name=author_name,
                    author_url=author_url
                )
                LOGGER.info('HTTP Request: POST https://api.graph.org/createPage/ "HTTP/1.1 200 OK"')
                return page["url"].replace("telegra.ph", "graph.org")
            except Exception as e:
                LOGGER.error(f'HTTP Request: POST https://api.graph.org/createPage/ "HTTP/1.1 500 Failed": {e}')
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue

        LOGGER.error("Failed to create Telegraph page after maximum retries")
        return None