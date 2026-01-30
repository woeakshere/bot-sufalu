import logging
import threading
import uvicorn
import asyncio
import time
import signal
from fastapi import FastAPI
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from telegram.error import Conflict, NetworkError
from config import Config

# --- IMPORT ALL HANDLERS ---
from bot.handlers import (
    start, 
    search, 
    torrent_command, 
    stats_command, 
    button_callback, 
    set_thumb_command, 
    broadcast_command
)

# --- IMPORT MEMORY MANAGER ---
from utils.memory_manager import start_memory_manager

# --- SILENT LOGGING SETUP ---
# We keep this minimal to save disk space on cloud logs
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.WARNING, 
    handlers=[logging.StreamHandler()]
)

# Silence specific noisy libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("uvicorn").setLevel(logging.CRITICAL)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("pymongo").setLevel(logging.WARNING)

# Enable INFO for this script only (so we can see startup messages)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- HEALTH CHECK SERVER (For Koyeb/Render) ---
app = FastAPI()

@app.get("/")
@app.get("/health")
async def health_check():
    return {
        "status": "active", 
        "bot": Config.BOT_USERNAME, 
        "platform": "Koyeb/Docker"
    }

def run_web_server():
    """Runs the lightweight web server in a background thread."""
    uvicorn.run(app, host="0.0.0.0", port=Config.PORT, log_level="critical")

# --- MAIN BOT EXECUTION ---
def main():
    # 1. Start Web Server (Daemon Thread)
    server_thread = threading.Thread(target=run_web_server, daemon=True)
    server_thread.start()

    # 2. Validate Token
    if not Config.BOT_TOKEN:
        logger.error("❌ BOT_TOKEN not found! Check your environment variables.")
        time.sleep(3600) # Sleep to prevent rapid crash loops
        return

    # 3. Initialize Bot
    application = ApplicationBuilder().token(Config.BOT_TOKEN).build()

    # 4. Register All Commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("search", search))
    application.add_handler(CommandHandler("torrent", torrent_command))
    application.add_handler(CommandHandler("setthumb", set_thumb_command))   # Feature: Custom Thumbnails
    application.add_handler(CommandHandler("broadcast", broadcast_command)) # Feature: Admin Broadcast
    
    # 5. Register Button Handler (Menu, Download, Cancel, etc.)
    application.add_handler(CallbackQueryHandler(button_callback))

    # 6. Start Memory Manager (Background Task)
    loop = asyncio.get_event_loop()
    loop.create_task(start_memory_manager())

    print(f"🚀 Bot Started as @{Config.BOT_USERNAME}...")

    # 7. ROBUST STARTUP LOOP (The "Conflict" Fix)
    # This loop tries to start the bot. If it hits a "Conflict" (old bot still running),
    # it waits 10 seconds and tries again, instead of crashing.
    while True:
        try:
            # stop_signals: Tells the bot to close cleanly when Koyeb sends SIGTERM
            # close_loop=False: Allows us to restart the loop if it crashes
            application.run_polling(
                stop_signals=[signal.SIGTERM, signal.SIGINT], 
                close_loop=False
            )
            break # If we exit cleanly, break the loop
        
        except Conflict:
            logger.warning("❌ Conflict Error: Old instance is still active.")
            logger.warning("⏳ Waiting 10 seconds for old instance to die...")
            time.sleep(10)
        
        except NetworkError:
            logger.error("❌ Network Error. Retrying in 5 seconds...")
            time.sleep(5)
            
        except Exception as e:
            logger.error(f"❌ Critical Error: {e}")
            logger.info("🔄 Restarting bot in 5 seconds...")
            time.sleep(5)

if __name__ == '__main__':
    main()
