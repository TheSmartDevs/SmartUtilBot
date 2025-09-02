import os
from dotenv import load_dotenv

load_dotenv()

def get_env_or_default(key, default=None, cast_func=str):
    value = os.getenv(key)
    if value is not None and value.strip() != "":
        try:
            return cast_func(value)
        except (ValueError, TypeError) as e:
            print(f"Error casting {key} with value '{value}' to {cast_func.__name__}: {e}")
            return default
    return default

API_ID = get_env_or_default("API_ID", "Your_API_ID_Here")
API_HASH = get_env_or_default("API_HASH", "Your_API_HASH_Here")
BOT_TOKEN = get_env_or_default("BOT_TOKEN", "Your_BOT_TOKEN_Here")
SESSION_STRING = get_env_or_default("SESSION_STRING", "Your_SESSION_STRING_Here")
OWNER_ID = get_env_or_default("OWNER_ID", "Your_OWNER_ID_Here", int)
DEVELOPER_USER_ID = get_env_or_default("DEVELOPER_USER_ID", "Your_DEVELOPER_USER_ID_Here", int)
MONGO_URL = get_env_or_default("MONGO_URL", "Your_MONGO_URL_Here")
DATABASE_URL = get_env_or_default("DATABASE_URL", "Your_DATABASE_URL_Here")
OPENAI_API_KEY = get_env_or_default("OPENAI_API_KEY", "Your_OPENAI_API_KEY_Here")
REPLICATE_API_TOKEN = get_env_or_default("REPLICATE_API_TOKEN", "Your_REPLICATE_API_TOKEN_Here")
GOOGLE_API_KEY = get_env_or_default("GOOGLE_API_KEY", "Your_GOOGLE_API_KEY_Here")
OCR_API_KEY = get_env_or_default("OCR_API_KEY", "Your_OCR_API_KEY_Here")
TRANS_API_KEY = get_env_or_default("TRANS_API_KEY", "Your_TRANS_API_KEY_Here")
MODEL_NAME = get_env_or_default("MODEL_NAME", "gemini-2.0-flash")
CC_SCRAPPER_LIMIT = get_env_or_default("CC_SCRAPPER_LIMIT", 5000, int)
SUDO_CCSCR_LIMIT = get_env_or_default("SUDO_CCSCR_LIMIT", 10000, int)
MULTI_CCSCR_LIMIT = get_env_or_default("MULTI_CCSCR_LIMIT", 2000, int)
MAIL_SCR_LIMIT = get_env_or_default("MAIL_SCR_LIMIT", 10000, int)
SUDO_MAILSCR_LIMIT = get_env_or_default("SUDO_MAILSCR_LIMIT", 15000, int)
CC_GEN_LIMIT = get_env_or_default("CC_GEN_LIMIT", 2000, int)
MULTI_CCGEN_LIMIT = get_env_or_default("MULTI_CCGEN_LIMIT", 5000, int)
A360APIBASEURL = get_env_or_default("A360APIBASEURL", "https://a360api-c8fbf2fa3cda.herokuapp.com")
GROQ_API_KEY = get_env_or_default("GROQ_API_KEY", "Your_GROQ_API_KEY_Here")
GROQ_API_URL = get_env_or_default("GROQ_API_URL", "https://api.groq.com/openai/v1/chat/completions")
DOMAIN_API_KEY = get_env_or_default("DOMAIN_API_KEY", "Your_DOMAIN_API_KEY_Here")
DOMAIN_API_URL = get_env_or_default("DOMAIN_API_URL", "https://www.whoisxmlapi.com/whoisserver/WhoisService")
TEXT_MODEL = get_env_or_default("TEXT_MODEL", "deepseek-r1-distill-llama-70b")
NEWS_API_KEY = get_env_or_default("NEWS_API_KEY", "Your_NEWS_API_KEY_Here")
raw_prefixes = get_env_or_default("COMMAND_PREFIX", "!|.|#|,|/")
COMMAND_PREFIX = [prefix.strip() for prefix in raw_prefixes.split("|") if prefix.strip()]
UPDATE_CHANNEL_URL = get_env_or_default("UPDATE_CHANNEL_URL", "https://t.me/TheSmartDev")
LOG_CHANNEL_ID = get_env_or_default("LOG_CHANNEL_ID", "-1002735511721")
IMGAI_SIZE_LIMIT = get_env_or_default("IMGAI_SIZE_LIMIT", 5242880, int)
MAX_TXT_SIZE = get_env_or_default("MAX_TXT_SIZE", 15728640, int)
MAX_VIDEO_SIZE = get_env_or_default("MAX_VIDEO_SIZE", 2147483648, int)
YT_COOKIES_PATH = get_env_or_default("YT_COOKIES_PATH", "./cookies/ISmartToolBot.txt")
VIDEO_RESOLUTION = get_env_or_default("VIDEO_RESOLUTION", "1280x720", lambda x: tuple(map(int, x.split('x'))))
DOMAIN_CHK_LIMIT = get_env_or_default("DOMAIN_CHK_LIMIT", 20, int)
PROXY_CHECK_LIMIT = get_env_or_default("PROXY_CHECK_LIMIT", 20, int)
BAN_REPLY = get_env_or_default("BAN_REPLY", "**Sorry Bro You're Banned From Using Me ❌**")

required_vars = {
    "API_ID": API_ID,
    "API_HASH": API_HASH,
    "BOT_TOKEN": BOT_TOKEN,
    "SESSION_STRING": SESSION_STRING,
    "OWNER_ID": OWNER_ID,
    "DEVELOPER_USER_ID": DEVELOPER_USER_ID,
    "MONGO_URL": MONGO_URL,
    "DATABASE_URL": DATABASE_URL
}

for var_name, var_value in required_vars.items():
    if var_value is None or var_value == f"Your_{var_name}_Here" or (isinstance(var_value, str) and var_value.strip() == ""):
        raise ValueError(f"Required variable {var_name} is missing or invalid. Set it in .env (VPS), config.py (VPS), or Heroku config vars.")

print("Loaded COMMAND_PREFIX:", COMMAND_PREFIX)
gpt_api_key_source = "environment variable" if os.getenv("OPENAI_API_KEY") else "config default"
print(f"OPENAI_API_KEY loaded from {gpt_api_key_source}: {'*' * 10}{OPENAI_API_KEY[-10:]}")

if not COMMAND_PREFIX:
    raise ValueError("No command prefixes found. Set COMMAND_PREFIX in .env, config.py, or Heroku config vars.")
