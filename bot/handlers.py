import os
import shutil
import logging
import time
import traceback
import signal
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

# --- LOGGING ---
logging.basicConfig(
    level=logging.WARNING, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
# Silence noisy libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("pymongo").setLevel(logging.WARNING)

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
    try:
        log_content = f"⚠️ Error:\n{error_msg}\n\nTrace:\n{traceback.format_exc()}"
        with open("error_log.txt", "w", encoding="utf-8") as f:
            f.write(log_content)
        
        chat_id = update.effective_chat.id if update.effective_chat else Config.CHANNEL_ID
        with open("error_log.txt", "rb") as f:
            await context.bot.send_document(chat_id=chat_id, document=f, caption="⚠️ **Error Log**")
        os.remove("error_log.txt")
    except: pass

# --- COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 **Leech Bot Active**\n\n"
        "/search <name> - Find anime\n"
        "/torrent <link> - Direct download\n"
        "/setthumb - Reply to photo to set custom thumbnail\n"
        "/stats - Bot health", 
        parse_mode="Markdown"
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔄 Checking...")
    
    # LAZY IMPORT: Only loads psutil when command is run
    import psutil 
    
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory()
    total_users = await db.get_total_users()
    down, up = await db.get_total_traffic()
    
    text = (
        f"📊 **Status**\n"
        f"**CPU**: `{cpu}%` | **RAM**: `{ram.percent}%`\n"
        f"**Users**: `{total_users}`\n"
        f"**Traffic**: ⬇️ `{human_readable_size(down)}` | ⬆️ `{human_readable_size(up)}`"
    )
    await msg.edit_text(text, parse_mode="Markdown")

async def set_thumb_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sets a custom thumbnail for the user."""
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        return await update.message.reply_text("❌ Reply to a photo to set it as thumbnail.")
    
    msg = await update.message.reply_text("⬇️ Downloading photo...")
    
    # Download photo to memory (not disk)
    photo = await update.message.reply_to_message.photo[-1].get_file()
    photo_bytes = await photo.download_as_bytearray()
    
    # Save to DB
    await db.set_thumbnail(update.effective_user.id, photo_bytes)
    await msg.edit_text("✅ **Thumbnail Saved!**\nIt will appear on your next upload.", parse_mode="Markdown")

# --- CORE LOGIC ---
async def monitor_and_process_download(gid, update, context, status_msg):
    try:
        async def progress_callback(status):
            try:
                p = status['progress']
                # Only edit if percentage changes significantly to save API calls
                if int(float(p)) % 5 == 0: 
                    await status_msg.edit_text(f"📥 **Downloading...** {p}%", parse_mode="Markdown")
            except: pass

        await downloader.wait_for_completion(gid, callback=progress_callback)

        status = await downloader.get_status(gid)
        if status and status["status"] == "complete":
            await status_msg.edit_text("✅ Downloaded. Processing...")
            base_path = f"./downloads/{status['name']}"
            user_id = update.effective_user.id
            
            if os.path.exists(base_path):
                files = []
                if os.path.isfile(base_path): files.append(base_path)
                else:
                    for r, _, f in os.walk(base_path):
                        for file in f:
                            if file.lower().endswith(('.mkv', '.mp4', '.avi', '.webm')):
                                files.append(os.path.join(r, file))
                    files.sort()

                if not files:
                    await status_msg.edit_text("⚠️ No video files.")
                    if os.path.isdir(base_path): shutil.rmtree(base_path)
                    return

                await status_msg.edit_text(f"Found {len(files)} files.")
                
                last_anime = None
                last_ep = None
                
                # Pre-fetch thumbnail once to save DB calls in loop
                thumb_data = await db.get_thumbnail(user_id)

                for idx, v_path in enumerate(files):
                    fname = os.path.basename(v_path)
                    final_path = v_path
                    sub_path = None
                    
                    # Check Subtitles
                    base = os.path.splitext(v_path)[0]
                    for ext in [".srt", ".vtt", ".ass"]:
                        if os.path.exists(base + ext):
                            sub_path = base + ext
                            break
                    
                    if sub_path:
                        # LAZY IMPORT: Only load Muxer if subtitles exist
                        try:
                            from processor.muxer import mux_subtitles
                            await status_msg.edit_text(f"🛠️ **Muxing...**")
                            out_muxed = base + "_muxed" + os.path.splitext(v_path)[1]
                            if mux_subtitles(v_path, sub_path, out_muxed):
                                final_path = out_muxed
                                fname = os.path.basename(final_path)
                        except ImportError:
                            logger.warning("Muxer not found.")

                    # Upload
                    try:
                        await status_msg.edit_text(f"⬆️ **Uploading ({idx+1}/{len(files)})**")
                        
                        with open(final_path, 'rb') as doc:
                            # ATTACH THUMBNAIL HERE
                            await context.bot.send_document(
                                Config.CHANNEL_ID, 
                                document=doc, 
                                caption=f"📂 `{fname}`", 
                                thumbnail=thumb_data, # <--- Used here
                                parse_mode="Markdown"
                            )
                        
                        anime, ep = await db.add_history(user_id, fname)
                        if anime: last_anime, last_ep = anime, ep
                        
                        fsize = os.path.getsize(final_path)
                        await db.update_stats(user_id, fsize, fsize)
                        
                        # Auto-Cleanup DB for batches
                        if idx == len(files) - 1 and len(files) > 1 and last_anime:
                            await db.delete_history(user_id, last_anime)
                            last_anime = None
                            
                        # Delete Files
                        if os.path.exists(final_path): os.remove(final_path)
                        if final_path != v_path and os.path.exists(v_path): os.remove(v_path)
                        if sub_path and os.path.exists(sub_path): os.remove(sub_path)
                        
                    except Exception as e:
                        logger.error(f"Upload failed: {e}")
                
                if os.path.isdir(base_path): shutil.rmtree(base_path)
                
                # Success Msg
                txt = "✅ **Done!**"
                if last_anime and last_ep:
                    txt += f"\n\n📺 **Tracked**: {last_anime} (Ep {last_ep})"
                    btn = [[InlineKeyboardButton(f"⏭️ Ep {last_ep+1}", callback_data=f"next_{last_anime} {last_ep+1}")]]
                    await status_msg.edit_text(txt, reply_markup=InlineKeyboardMarkup(btn), parse_mode="Markdown")
                else:
                    await status_msg.edit_text(txt, parse_mode="Markdown")
            else:
                await status_msg.edit_text("❌ File missing.")
        else:
            await status_msg.edit_text("❌ Download failed.")
            
    except Exception as e:
        logger.error(f"Critical: {e}")
        await send_error_log(update, context, str(e))

# --- USER COMMANDS (Unchanged) ---
async def torrent_command(update, context):
    if not context.args: return await update.message.reply_text("❌ `/torrent <link>`")
    msg = await update.message.reply_text("⚡ Initializing...")
    gid = await downloader.add_torrent(context.args[0])
    if gid: await monitor_and_process_download(gid, update, context, msg)
    else: await msg.edit_text("❌ Failed.")

async def search(update, context):
    if not context.args: return await update.message.reply_text("❌ `/search <anime>`")
    q = " ".join(context.args)
    msg = await update.message.reply_text("🔍 Searching...")
    res = []
    
    try: res = await CommonAnimeScraper().run(q)
    except: pass
    if not res:
        try: res = await scrape_gogoanime(q)
        except: pass
    if not res:
        try: res = await AnimeBot().run(q)
        except: pass
        
    if not res: return await msg.edit_text("❌ None found.")
    
    kb = []
    for r in res[:10]:
        t = r.get("title", "?")[:40]
        p = "lnk" if r.get("type") == "link" else "vid"
        kb.append([InlineKeyboardButton(f"🎬 {t}", callback_data=f"{p}_{r.get('url')}")])
        
    await msg.edit_text(f"✅ Results: **{q}**", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

async def button_callback(update, context):
    q = update.callback_query
    await q.answer()
    d = q.data
    
    if d.startswith("vid_"):
        u = d.split("_", 1)[1]
        k = [[InlineKeyboardButton(x, callback_data=f"qual_{x}_{u}")] for x in ["1080p", "720p"]]
        await q.edit_message_text("Select Quality:", reply_markup=InlineKeyboardMarkup(k))
    elif d.startswith("lnk_"):
        await context.bot.send_message(Config.CHANNEL_ID, f"🔗 {d.split('_',1)[1]}")
        await q.edit_message_text("🔗 Sent to channel.")
    elif d.startswith("qual_"):
        u = d.split("_", 2)[-1]
        await q.edit_message_text("⚡ Downloading...")
        gid = await downloader.add_torrent(u)
        if gid: await monitor_and_process_download(gid, update, context, q.message)
    elif d.startswith("next_"):
        context.args = d.split("_", 1)[1].split(" ")
        await search(update, context)
