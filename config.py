import os
from dotenv import load_dotenv

# Load .env file if it exists (useful for local testing)
load_dotenv()

class Config:
    # --- TELEGRAM SETTINGS ---
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    BOT_USERNAME = os.getenv("BOT_USERNAME", "YourBotName")
    
    # 1. ADMIN MANAGEMENT (Supports Multiple Admins)
    # Accepts a comma-separated list: "12345678, 87654321"
    admin_str = os.getenv("ADMIN_IDS", "")
    ADMIN_IDS = [int(x) for x in admin_str.split(",") if x.strip().isdigit()]
    
    # Fallback: Check for old single ADMIN_ID variable
    if os.getenv("ADMIN_ID"):
        try:
            ADMIN_IDS.append(int(os.getenv("ADMIN_ID")))
        except ValueError:
            pass
    
    # Remove duplicates
    ADMIN_IDS = list(set(ADMIN_IDS))

    # Channel ID for File Uploads (Must be an integer, usually negative)
    try:
        CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
    except ValueError:
        CHANNEL_ID = 0

    # --- DATABASE SETTINGS ---
    MONGO_URL = os.getenv("MONGO_URL")
    DB_NAME = os.getenv("DB_NAME", "anime_bot")

    # --- SERVER SETTINGS ---
    # Port is required by Koyeb/Render/Heroku health checks
    PORT = int(os.getenv("PORT", "8000"))

    # --- PERFORMANCE TUNING ---
    # Worker Recycling: Restarts the bot after N downloads to clear memory leaks.
    # Set to 0 to disable. Recommended: 10-20 for 512MB RAM.
    WORKER_TTL = int(os.getenv("WORKER_TTL", "20"))
