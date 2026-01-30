import logging
import threading
import uvicorn
import asyncio
from fastapi import FastAPI
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from config import Config

# Import Handlers
from bot.handlers import start, search, torrent_command, stats_command, button_callback
from utils.memory_manager import start_memory_manager

# --- SILENT LOGGING ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.WARNING # Only show critical warnings
)
# Silence specific noisy libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("uvicorn").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

# --- HEALTH CHECK SERVER ---
app = FastAPI()

@app.get("/")
@app.get("/health")
async def health_check():
    return {"status": "active"}

def run_web_server():
    # log_level="critical" ensures uvicorn doesn't spam console
    uvicorn.run(app, host="0.0.0.0", port=Config.PORT, log_level="critical")

# --- MAIN BOT ---
def main():
    server_thread = threading.Thread(target=run_web_server, daemon=True)
    server_thread.start()

    if not Config.BOT_TOKEN:
        logger.error("❌ BOT_TOKEN not found!")
        import time; time.sleep(3600); return
        
    application = ApplicationBuilder().token(Config.BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("search", search))
    application.add_handler(CommandHandler("torrent", torrent_command))
    application.add_handler(CallbackQueryHandler(button_callback))

    print(f"🚀 Bot Started as @{Config.BOT_USERNAME}...")
    
    # Start Memory Manager (Clean RAM/Disk)
    loop = asyncio.get_event_loop()
    loop.create_task(start_memory_manager())

    application.run_polling()

if __name__ == '__main__':
    main()
