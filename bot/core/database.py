from motor.motor_asyncio import AsyncIOMotorClient
from urllib.parse import urlparse, parse_qs
from config import DATABASE_URL
from bot.helpers.logger import LOGGER

LOGGER.info("Creating Database Client From DATABASE_URL")
try:
    parsed = urlparse(DATABASE_URL)
    query_params = parse_qs(parsed.query)
    db_name = query_params.get("appName", [None])[0]
    if not db_name:
        raise ValueError("No database name found in DATABASE_URL (missing 'appName' query param)")
    mongo_client = AsyncIOMotorClient(DATABASE_URL)
    db = mongo_client.get_database(db_name)
    SmartGuards = db["SmartGuards"]
    SmartSecurity = db["SmartSecurity"]
    SmartReboot = db["SmartReboot"]
    LOGGER.info(f"Database Client Created Successfully!")
except Exception as e:
    LOGGER.error(f"Database Client Create Error: {e}")
    raise