import logging
import threading
import uvicorn
from fastapi import FastAPI
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler
from config import Config

# Import Handlers
from bot.handlers import start, search, torrent_command, stats_command, button_callback

# Configure Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- HEALTH CHECK SERVER (FastAPI) ---
# This satisfies Koyeb/Render's "Port 8000" requirement
app = FastAPI()

@app.get("/")
@app.get("/health")
async def health_check():
    """
    Ping endpoint for Cloud Providers.
    Returns 200 OK to keep the bot alive.
    """
    return {
        "status": "active", 
        "bot": Config.BOT_USERNAME, 
        "mode": "production"
    }

def run_web_server():
    """
    Runs Uvicorn in a separate daemon thread.
    """
    logger.info(f"🌍 Health Check Server starting on Port {Config.PORT}")
    # log_level="error" keeps the console clean
    uvicorn.run(app, host="0.0.0.0", port=Config.PORT, log_level="error")

# --- MAIN BOT EXECUTION ---
def main():
    """
    Initializes the Bot and starts the background Web Server.
    """
    # 1. Start Web Server first (Ensures Health Check passes on Koyeb/Render)
    server_thread = threading.Thread(target=run_web_server, daemon=True)
    server_thread.start()

    # 2. Initialize Bot Application
    if not Config.BOT_TOKEN:
        logger.error("❌ BOT_TOKEN not found! Please set it in environment variables.")
        # Keep the thread alive so the web server continues to run
        import time
        while True:
            time.sleep(3600)
        return
    application = ApplicationBuilder().token(Config.BOT_TOKEN).build()

    # 2. Register Command Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("stats", stats_command))     # Admin Stats
    application.add_handler(CommandHandler("search", search))           # Search Engine
    application.add_handler(CommandHandler("torrent", torrent_command)) # Direct Download

    # 3. Register Button Handler (Quality Menu, Next Ep, etc.)
    application.add_handler(CallbackQueryHandler(button_callback))

    # 4. Start Everything
    print(f"🚀 Bot Started as @{Config.BOT_USERNAME}...")
    
    # Start Polling (Blocking call - keeps the script running)
    application.run_polling()

if __name__ == '__main__':
    main()