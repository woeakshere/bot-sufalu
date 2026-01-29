import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram Secrets
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    BOT_USERNAME = os.getenv("BOT_USERNAME", "LeechBot")
    
    # Handle CHANNEL_ID safely
    channel_id_raw = os.getenv("CHANNEL_ID")
    CHANNEL_ID = int(channel_id_raw) if channel_id_raw and channel_id_raw.strip('-').isdigit() else 0
    
    # Database
    MONGO_URL = os.getenv("MONGO_URL")
    DB_NAME = os.getenv("DB_NAME", "leechbot_db")
    
    # Aria2
    ARIA2_RPC_URL = os.getenv("ARIA2_RPC_URL", "http://localhost:6800/rpc")
    ARIA2_SECRET = os.getenv("ARIA2_SECRET", "")
    
    # Server Configuration
    # Koyeb/Render usually provide a PORT env var, default to 8000 which is common for health checks
    PORT = int(os.environ.get("PORT", 8000))
