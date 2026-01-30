import logging
import threading
import uvicorn
import asyncio
import time
import signal
from fastapi import FastAPI
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from telegram.error import Conflict
from config import Config

# Import Handlers
from bot.handlers import start, search, torrent_command, stats_command, button_callback, set_thumb_command
# Import Memory Manager
from utils.memory_manager import start_memory_manager

# --- SILENT LOGGING SETUP ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.WARNING,
    handlers=[logging.StreamHandler()]
)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("uvicorn").setLevel(logging.CRITICAL)
logging.getLogger("apscheduler").setLevel(logging.WARNING)
logging.getLogger("pymongo").setLevel(logging.WARNING)
# Enable INFO for this specific script so we can see the retry messages
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- HEALTH CHECK SERVER ---
app = FastAPI()

@app.get("/")
@app.get("/health")
async def health_check():
    return {"status": "active", "bot": Config.BOT_USERNAME}

def run_web_server():
    uvicorn.run(app, host="0.0.0.0", port=Config.PORT, log_level="critical")

# --- MAIN BOT EXECUTION ---
def main():
    # 1. Start Web Server
    server_thread = threading.Thread(target=run_web_server, daemon=True)
    server_thread.start()

    # 2. Validate Token
    if not Config.BOT_TOKEN:
        logger.error("❌ BOT_TOKEN not found!")
        time.sleep(3600)
        return

    # 3. Initialize Bot
    application = ApplicationBuilder().token(Config.BOT_TOKEN).build()

    # 4. Register Commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("search", search))
    application.add_handler(CommandHandler("torrent", torrent_command))
    application.add_handler(CommandHandler("setthumb", set_thumb_command)) # <-- NEW
    application.add_handler(CallbackQueryHandler(button_callback))

    # 5. Start Memory Manager
    loop = asyncio.get_event_loop()
    loop.create_task(start_memory_manager())

    print(f"🚀 Bot Started as @{Config.BOT_USERNAME}...")

    # 6. SHUTDOWN CONFIGURATION
    application.run_polling(stop_signals=[signal.SIGTERM, signal.SIGINT])

if __name__ == '__main__':
    main()
