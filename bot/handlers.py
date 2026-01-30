import os
import shutil
import logging
import time
import psutil
import traceback
# REMOVED: from logging.handlers import RotatingFileHandler (Saves Disk Space)
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

# --- SCRAPER IMPORTS ---
from scrapers.common_scraper import CommonAnimeScraper
from scrapers.gogoanime3 import scrape_gogoanime
from scrapers.animixplay import scrape_animixplay
from scrapers.allanime import AnimeBot

# --- CORE IMPORTS ---
from downloader.torrent import TorrentDownloader
from database.mongo import db
from config import Config

# --- OPTIONAL: IMPORT MUXER ---
try:
    from processor.muxer import mux_subtitles
except ImportError:
    mux_subtitles = None
    print("⚠️ Warning: processor.muxer not found. Muxing disabled.")

# --- LOGGING SETUP (OPTIMIZED) ---
# 1. Level=WARNING (Hides "Downloading..." spam)
# 2. No FileHandler (Saves Disk Space)
logging.basicConfig(
    level=logging.WARNING, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler() # Only print to console (Koyeb handles this natively)
    ]
)
# Reduce chatter from third-party libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("pymongo").setLevel(logging.WARNING)
logging.getLogger("apscheduler").setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

downloader = TorrentDownloader()
BOT_START_TIME = time.time()

# --- HELPER FUNCTIONS ---
def get_progress_bar(percentage, length=10):
    try:
        if isinstance(percentage, str): percentage = float(percentage.replace('%', ''))
        filled = int(length * percentage // 100)
        return "▰" * filled + "▱" * (length - filled)
    except: return "▱" * length

def human_readable_size(size, decimal_places=2):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0: return f"{size:.{decimal_places}f} {unit}"
        size /= 1024.0
    return f"{size:.{decimal_places}f} PB"

def get_uptime():
    seconds = int(time.time() - BOT_START_TIME)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    return f"{days}d {hours}h {minutes}m {seconds}s"

async def send_error_log(update, context, error_msg):
    """Generates a text file with the error trace and sends it to the user."""
    try:
        log_content = f"⚠️ Error Occurred:\n{error_msg}\n\nTraceback:\n{traceback.format_exc()}"
        with open("error_log.txt", "w", encoding="utf-8") as f:
            f.write(log_content)
        
        chat_id = update.effective_chat.id if update.effective_chat else Config.CHANNEL_ID
        with open("error_log.txt", "rb") as f:
            await context.bot.send_document(
                chat_id=chat_id, 
                document=f, 
                caption="⚠️ **Bot Error Log**"
            )
        os.remove("error_log.txt")
    except Exception:
        logger.error("Failed to send error log to user.")

# --- COMMAND HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 **Leech Bot is Active**\n\n"
        "Commands:\n"
        "/search <anime> - Find episodes\n"
        "/torrent <link> - Direct download\n"
        "/stats - Server health",
        parse_mode="Markdown"
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # LAZY IMPORT (Saves Startup RAM)
    import psutil
    
    msg = await update.message.reply_text("🔄 Checking stats...")
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory()
    total_users = await db.get_total_users()
    down, up = await db.get_total_traffic()
    
    text = (
        f"📊 **System Status**\n"
        f"**Uptime**: `{get_uptime()}`\n"
        f"**CPU**: `{cpu}%` | **RAM**: `{ram.percent}%`\n\n"
        f"🤖 **Bot Usage**\n"
        f"**Users**: `{total_users}`\n"
        f"**Traffic**: ⬇️ `{human_readable_size(down)}` | ⬆️ `{human_readable_size(up)}`"
    )
    await msg.edit_text(text, parse_mode="Markdown")

# --- CORE PROCESSING ENGINE ---
async def monitor_and_process_download(gid, update, context, status_msg):
    try:
        async def progress_callback(status):
            # Only update Telegram message, don't log to console
            try:
                p = status['progress']
                # Throttle updates to avoid Telegram rate limits (every 5% or similar logic is implicit in aria2 wrapper)
                await status_msg.edit_text(
                    f"📥 **Downloading...**\n"
                    f"📂 `{status['name']}`\n"
                    f"{get_progress_bar(p)} **{p}%**\n"
                    f"🚀 `{status['speed']}` | ⏳ `{status.get('eta', 'N/A')}`",
                    parse_mode="Markdown"
                )
            except: pass

        await downloader.wait_for_completion(gid, callback=progress_callback)

        status = await downloader.get_status(gid)
        if status and status["status"] == "complete":
            await status_msg.edit_text("✅ Download complete. Preparing files...")
            base_path = f"./downloads/{status['name']}"
            user_id = update.effective_user.id
            
            if os.path.exists(base_path):
                files_to_upload = []

                if os.path.isfile(base_path):
                    files_to_upload.append(base_path)
                elif os.path.isdir(base_path):
                    for root, _, filenames in os.walk(base_path):
                        for filename in filenames:
                            if filename.lower().endswith(('.mkv', '.mp4', '.avi', '.webm')):
                                files_to_upload.append(os.path.join(root, filename))
                    files_to_upload.sort()

                if not files_to_upload:
                    await status_msg.edit_text("⚠️ No video files found.")
                    if os.path.isdir(base_path): shutil.rmtree(base_path)
                    elif os.path.isfile(base_path): os.remove(base_path)
                    return

                await status_msg.edit_text(f"Found {len(files_to_upload)} files. Processing...")

                last_anime_name = None
                last_ep_num = None
                total_files = len(files_to_upload)

                for index, video_path in enumerate(files_to_upload):
                    file_name = os.path.basename(video_path)
                    final_path = video_path
                    sub_path = None
                    
                    # Auto-Muxing
                    base_name = os.path.splitext(video_path)[0]
                    for ext in [".srt", ".vtt", ".ass"]:
                        if os.path.exists(base_name + ext):
                            sub_path = base_name + ext
                            break
                    
                    if sub_path and mux_subtitles:
                        await status_msg.edit_text(f"🛠️ **Muxing...**\n`{file_name}`")
                        output_ext = os.path.splitext(video_path)[1]
                        output_muxed = base_name + "_muxed" + output_ext
                        
                        success = mux_subtitles(video_path, sub_path, output_muxed)
                        if success:
                            final_path = output_muxed
                            file_name = os.path.basename(final_path)
                        else:
                            # Log warning only if muxing fails
                            logger.warning(f"Muxing failed for {file_name}, reverting to original.")

                    # Upload
                    file_size = os.path.getsize(final_path)
                    try:
                        await status_msg.edit_text(f"⬆️ **Uploading ({index+1}/{total_files})**", parse_mode="Markdown")
                        
                        with open(final_path, 'rb') as doc:
                            await context.bot.send_document(
                                chat_id=Config.CHANNEL_ID,
                                document=doc,
                                caption=f"✨ **Upload Complete**\n📂 `{file_name}`",
                                parse_mode="Markdown"
                            )
                        
                        anime_name, last_ep = await db.add_history(user_id, file_name)
                        if anime_name: 
                            last_anime_name = anime_name
                            last_ep_num = last_ep
                            
                        await db.update_stats(user_id, bytes_downloaded=file_size, bytes_uploaded=file_size)

                        if index == total_files - 1 and total_files > 1:
                            if last_anime_name:
                                await status_msg.edit_text(f"♻️ **Cleaning DB...**", parse_mode="Markdown")
                                await db.delete_history(user_id, last_anime_name)
                                last_anime_name = None

                        if os.path.exists(final_path): os.remove(final_path)
                        if final_path != video_path and os.path.exists(video_path): os.remove(video_path)
                        if sub_path and os.path.exists(sub_path): os.remove(sub_path)

                    except Exception as e:
                        logger.error(f"Upload failed: {e}")
                        await send_error_log(update, context, f"Upload Failed: {e}")

                if os.path.isdir(base_path):
                    shutil.rmtree(base_path)

                completion_text = "✅ **Done!**"
                buttons = []
                if last_anime_name and last_ep_num:
                    next_ep = last_ep_num + 1
                    query_str = f"{last_anime_name} {next_ep}"
                    completion_text += f"\n\n📺 **Tracked**: {last_anime_name} (Ep {last_ep_num})"
                    buttons.append([InlineKeyboardButton(f"⏭️ Ep {next_ep}", callback_data=f"next_{query_str}")])

                if buttons:
                    await status_msg.edit_text(completion_text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="Markdown")
                else:
                    await status_msg.edit_text(completion_text, parse_mode="Markdown")

            else:
                await status_msg.edit_text("❌ Error: File not found.")
        else:
            await status_msg.edit_text("❌ Download failed.")

    except Exception as e:
        logger.error(f"Critical Error: {e}")
        await status_msg.edit_text("⚠️ Critical Error.")
        await send_error_log(update, context, str(e))

async def torrent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("❌ Usage: `/torrent <link>`", parse_mode="Markdown")
    
    link = context.args[0]
    status_msg = await update.message.reply_text("⚡ Initializing...")
    
    try:
        gid = await downloader.add_torrent(link)
        if gid:
            await monitor_and_process_download(gid, update, context, status_msg)
        else:
            await status_msg.edit_text("❌ Failed to add torrent.")
    except Exception as e:
        await send_error_log(update, context, str(e))

async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        return await update.message.reply_text("❌ Usage: `/search <anime>`", parse_mode="Markdown")
    
    query = " ".join(context.args)
    status_msg = await update.message.reply_text(f"🔍 Searching...")
    results = []
    
    try: results = await CommonAnimeScraper().run(query) 
    except: pass
    
    if not results:
        try: results = await scrape_gogoanime(query)
        except: pass
    
    if not results:
        try: results = await AnimeBot().run(query)
        except: pass

    if not results:
        return await status_msg.edit_text("❌ No results found.")

    keyboard = []
    for res in results[:10]:
        title = res.get("title", "Unknown")[:40]
        url = res.get("url", "")
        rtype = res.get("type", "video")
        prefix = "lnk" if rtype == "link" else "doc" if rtype == "file" else "vid"
        icon = "🔗" if rtype == "link" else "📂" if rtype == "file" else "🎬"
        keyboard.append([InlineKeyboardButton(f"{icon} {title}", callback_data=f"{prefix}_{url}")])

    await status_msg.edit_text(f"✅ Results for **{query}**:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    
    try:
        if data.startswith("vid_"):
            url = data.split("_", 1)[1]
            keyboard = [[InlineKeyboardButton(q, callback_data=f"qual_{q}_{url}")] for q in ["1080p", "720p", "360p"]]
            await query.edit_message_text(f"🎬 Select Quality:", reply_markup=InlineKeyboardMarkup(keyboard))

        elif data.startswith("lnk_"):
            url = data.split("_", 1)[1]
            await query.edit_message_text("🔗 Link sent to channel.")
            await context.bot.send_message(Config.CHANNEL_ID, text=f"🚀 **Direct Link**\n{url}")

        elif data.startswith("qual_") or data.startswith("doc_"):
            url = data.split("_", 2)[-1] if data.startswith("qual") else data.split("_", 1)[1]
            await query.edit_message_text("⚡ Starting download...")
            gid = await downloader.add_torrent(url)
            if gid:
                await monitor_and_process_download(gid, update, context, query.message)
            else:
                await query.edit_message_text("❌ Download failed.")

        elif data.startswith("next_"):
            search_query = data.split("_", 1)[1]
            await query.edit_message_text(f"🔍 Searching Next Ep: `{search_query}`", parse_mode="Markdown")
            context.args = search_query.split(" ")
            await search(update, context)

    except Exception as e:
        await send_error_log(update, context, f"Error: {str(e)}")
