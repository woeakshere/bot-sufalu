import logging
import threading
import uvicorn
import asyncio
import time
from fastapi import FastAPI
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from config import Config

# Import Handlers
from bot.handlers import start, search, torrent_command, stats_command, button_callback
# Import Memory Manager
from utils.memory_manager import start_memory_manager

# --- SILENT LOGGING SETUP ---
# 1. Set global level to WARNING to hide "INFO" spam
# 2. Use StreamHandler to print to console only (No file writing = Saved Disk)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.WARNING,
    handlers=[logging.StreamHandler()]
)

# Silence specific noisy libraries that spam logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("uvicorn").setLevel(logging.CRITICAL) # Silence web server logs
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("pymongo").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# --- HEALTH CHECK SERVER (FastAPI) ---
# Required for Koyeb/Render to keep the bot alive
app = FastAPI()

@app.get("/")
@app.get("/health")
async def health_check():
    return {
        "status": "active", 
        "bot": Config.BOT_USERNAME,
        "mode": "production"
    }

def run_web_server():
    """Runs the lightweight web server in a background thread."""
    # log_level="critical" ensures uvicorn stays silent
    uvicorn.run(app, host="0.0.0.0", port=Config.PORT, log_level="critical")

# --- MAIN BOT EXECUTION ---
def main():
    """Orchestrates the Web Server, Memory Manager, and Telegram Bot."""
    
    # 1. Start Web Server (Daemon Thread)
    # We start this first so the cloud provider sees port 8000 active immediately
    server_thread = threading.Thread(target=run_web_server, daemon=True)
    server_thread.start()

    # 2. Validate Token
    if not Config.BOT_TOKEN:
        logger.error("❌ BOT_TOKEN not found! Please set it in config.py or env vars.")
        # Sleep to prevent crash loops if token is missing
        time.sleep(3600)
        return

    # 3. Initialize Bot
    application = ApplicationBuilder().token(Config.BOT_TOKEN).build()

    # 4. Register Commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats_command))     # Admin/User Stats
    application.add_handler(CommandHandler("search", search))           # Scraper Search
    application.add_handler(CommandHandler("torrent", torrent_command)) # Manual Torrent Add
    
    # 5. Register Button Handlers (Menus, Quality Select, Next Ep)
    application.add_handler(CallbackQueryHandler(button_callback))

    print(f"🚀 Bot Started as @{Config.BOT_USERNAME}...")
    
    # 6. Start Memory Manager (Background Task)
    # This cleans RAM and Disk every 60 seconds
    loop = asyncio.get_event_loop()
    loop.create_task(start_memory_manager())

    # 7. Start Polling (Blocking)
    application.run_polling()

if __name__ == '__main__':
    main()
