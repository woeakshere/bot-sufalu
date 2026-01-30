import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    
    # 1. SUPPORT MULTIPLE ADMINS
    # Input example in .env: ADMIN_IDS=12345678,98765432
    admin_str = os.getenv("ADMIN_IDS", "")
    ADMIN_IDS = [int(x) for x in admin_str.split(",") if x.strip().isdigit()]
    
    # Fallback: if user used the old ADMIN_ID var, add it too
    if os.getenv("ADMIN_ID"):
        ADMIN_IDS.append(int(os.getenv("ADMIN_ID")))

    CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
    MONGO_URL = os.getenv("MONGO_URL")
    DB_NAME = "anime_bot"
    BOT_USERNAME = os.getenv("BOT_USERNAME", "YourBotName")
    PORT = int(os.getenv("PORT", "8000"))
