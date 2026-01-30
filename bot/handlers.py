import os
import shutil
import logging
import time
import traceback
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, error as tg_error
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
from utils.memory_manager import start_memory_manager

# --- LOGGING ---
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("pymongo").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

downloader = TorrentDownloader()
BOT_START_TIME = time.time()

# --- WORKER STATE ---
JOBS_PROCESSED = 0
JOB_LOCK = asyncio.Lock()

# --- HELPER FUNCTIONS ---
def human_readable_size(size, decimal_places=2):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0: return f"{size:.{decimal_places}f} {unit}"
        size /= 1024.0
    return f"{size:.{decimal_places}f} PB"

async def async_delete(path):
    if not path or not os.path.exists(path): return
    try:
        if os.path.isfile(path):
            await asyncio.to_thread(os.remove, path)
        elif os.path.isdir(path):
            await asyncio.to_thread(shutil.rmtree, path)
    except Exception as e:
        logger.warning(f"Failed to delete {path}: {e}")

async def send_error_log(update, context, error_msg):
    try:
        log_content = f"⚠️ Error:\n{error_msg}\n\nTrace:\n{traceback.format_exc()}"
        with open("error_log.txt", "w", encoding="utf-8") as f:
            f.write(log_content)
        chat_id = update.effective_chat.id if update.effective_chat else Config.CHANNEL_ID
        with open("error_log.txt", "rb") as f:
            await context.bot.send_document(chat_id=chat_id, document=f, caption="⚠️ **Error Log**")
        await async_delete("error_log.txt")
    except Exception as e:
        logger.warning(f"Failed to send error log: {e}")

# --- COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 **Leech Bot Active**\n/search <name>\n/torrent <link>\n/stats",
        parse_mode="Markdown"
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔄 Checking...")
    import psutil
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory()
    total_users = await db.get_total_users()
    down, up = await db.get_total_traffic()
    
    text = (
        f"📊 **Status**\n"
        f"**CPU**: `{cpu}%` | **RAM**: `{ram.percent}%`\n"
        f"**Jobs**: `{JOBS_PROCESSED}/{Config.WORKER_TTL}`\n"
        f"**Users**: `{total_users}`\n"
        f"**Traffic**: ⬇️ `{human_readable_size(down)}` | ⬆️ `{human_readable_size(up)}`"
    )
    await msg.edit_text(text, parse_mode="Markdown")

async def set_thumb_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        return await update.message.reply_text("❌ Reply to a photo.")
    msg = await update.message.reply_text("⬇️ Downloading...")
    photo = await update.message.reply_to_message.photo[-1].get_file()
    photo_bytes = await photo.download_as_bytearray()
    await db.set_thumbnail(update.effective_user.id, photo_bytes)
    await msg.edit_text("✅ **Saved!**", parse_mode="Markdown")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in Config.ADMIN_IDS: return
    if not context.args: return await update.message.reply_text("❌ Usage: `/broadcast <msg>`")
    
    msg = " ".join(context.args)
    status = await update.message.reply_text("📢 **Sending...**", parse_mode="Markdown")
    total, success = 0, 0
    async for user in db.users.find({}):
        total += 1
        try:
            await context.bot.send_message(user['user_id'], f"📢 **Announcement:**\n\n{msg}", parse_mode="Markdown")
            success += 1
            await asyncio.sleep(0.05)
        except: pass
    await status.edit_text(f"✅ **Done** ({success}/{total})", parse_mode="Markdown")

# --- CORE LOGIC ---
async def monitor_and_process_download(gid, update, context, status_msg):
    global JOBS_PROCESSED
    created_files = []
    base_path = None

    try:
        cancel_btn = InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{gid}")]])

        async def progress_callback(status):
            try:
                if int(float(status['progress'])) % 5 == 0:
                    await status_msg.edit_text(
                        f"📥 **{status['progress']}%** | 🚀 `{status['speed']}`",
                        reply_markup=cancel_btn, parse_mode="Markdown"
                    )
            except: pass

        await downloader.wait_for_completion(gid, callback=progress_callback)
        status = await downloader.get_status(gid)

        if status and status["status"] == "complete":
            await status_msg.edit_text("✅ Processing...")
            base_path = f"./downloads/{status['name']}"
            created_files.append(base_path)

            # Discover video files
            video_files = []
            if os.path.isfile(base_path): video_files.append(base_path)
            else:
                for r, _, f in os.walk(base_path):
                    for file in f:
                        if file.lower().endswith(('.mkv', '.mp4', '.avi')):
                            video_files.append(os.path.join(r, file))
            video_files.sort()

            if not video_files:
                return await status_msg.edit_text("⚠️ No video files.")

            await status_msg.edit_text(f"Found {len(video_files)} files.")
            thumb_data = await db.get_thumbnail(update.effective_user.id)
            last_anime, last_ep = None, None

            for idx, v_path in enumerate(video_files):
                fname = os.path.basename(v_path)
                final_path = v_path

                # Subtitle muxing (.srt, .vtt, .ass)
                base = os.path.splitext(v_path)[0]
                sub_path = next((base + ext for ext in [".srt", ".vtt", ".ass"] if os.path.exists(base + ext)), None)
                if sub_path: created_files.append(sub_path)

                if sub_path:
                    try:
                        from processor.muxer import mux_subtitles
                        out_muxed = base + "_muxed" + os.path.splitext(v_path)[1]
                        created_files.append(out_muxed)
                        if mux_subtitles(v_path, sub_path, out_muxed):
                            final_path = out_muxed
                            fname = os.path.basename(final_path)
                    except Exception as e:
                        logger.warning(f"Muxing failed: {e}")

                # Upload with retries
                sent_msg = None
                for attempt in range(3):
                    try:
                        await status_msg.edit_text(f"⬆️ Uploading ({idx+1}/{len(video_files)}) | Attempt {attempt+1}/3")
                        with open(final_path, 'rb') as doc:
                            sent_msg = await context.bot.send_document(
                                Config.CHANNEL_ID, document=doc, caption=f"📂 `{fname}`",
                                thumbnail=thumb_data, parse_mode="Markdown"
                            )
                        break
                    except tg_error.NetworkError:
                        await asyncio.sleep(2 * (attempt + 1))
                    except Exception as e:
                        logger.error(f"Upload Error: {e}")
                        break

                if sent_msg:
                    anime, ep = await db.add_history(update.effective_user.id, fname)
                    if anime: last_anime, last_ep = anime, ep
                    await db.update_stats(update.effective_user.id, os.path.getsize(final_path))

                    if idx == len(video_files) - 1 and len(video_files) > 1 and last_anime:
                        await db.delete_history(update.effective_user.id, last_anime)

            # Worker Recycling
            if Config.WORKER_TTL > 0:
                async with JOB_LOCK:
                    JOBS_PROCESSED += 1
                    if JOBS_PROCESSED >= Config.WORKER_TTL:
                        await status_msg.reply_text("♻️ **Maintenance Restart...**")
                        await asyncio.sleep(2)
                        os._exit(0)

            txt = "✅ **Done!**"
            if last_anime: txt += f"\n📺 {last_anime} (Ep {last_ep})"
            await status_msg.edit_text(txt, parse_mode="Markdown")

        elif status and status["status"] == "removed":
            await status_msg.edit_text("❌ **Cancelled.**", parse_mode="Markdown")
        else:
            await status_msg.edit_text("❌ Failed.")

    except Exception as e:
        await send_error_log(update, context, str(e))

    finally:
        if base_path: await async_delete(base_path)
        for f in created_files: await async_delete(f)

# --- TORRENT COMMAND ---
async def torrent_command(update, context):
    if not context.args: return await update.message.reply_text("❌ `/torrent <link>`")
    msg = await update.message.reply_text("⚡ Initializing...")
    gid = await downloader.add_torrent(context.args[0])
    if gid: await monitor_and_process_download(gid, update, context, msg)
    else: await msg.edit_text("❌ Failed.")

# --- SEARCH COMMAND ---
async def search(update, context):
    if not context.args: return await update.message.reply_text("❌ `/search <anime>`")
    q = " ".join(context.args)
    msg = await update.message.reply_text("🔍 Searching...")
    res = []

    scrapers = [
        ("Common", CommonAnimeScraper().run(q)),
        ("Gogo", scrape_gogoanime(q)),
        ("Animix", scrape_animixplay(q)),
        ("AllAnime", AnimeBot().run(q))
    ]

    for name, task in scrapers:
        if res: break
        try:
            res = await asyncio.wait_for(task, timeout=10)
            logger.info(f"Scraper '{name}' succeeded with {len(res)} results.")
        except asyncio.TimeoutError:
            logger.warning(f"Scraper '{name}' timed out.")
        except Exception as e:
            logger.warning(f"Scraper '{name}' failed: {e}")

    if not res: return await msg.edit_text("❌ None found.")

    kb = []
    for r in res[:10]:
        t = r.get("title", "?")[:40]
        kb.append([InlineKeyboardButton(f"🎬 {t}", callback_data=f"vid_{r.get('url')}")])
    await msg.edit_text(f"✅ Results: **{q}**", reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")

# --- BUTTON CALLBACK ---
QUALITY_OPTIONS = ["1080p sub", "1080p dub", "720p sub", "720p dub"]

async def button_callback(update, context):
    q = update.callback_query
    await q.answer()
    d = q.data

    if d.startswith("vid_"):
        anime_url = d.split("_", 1)[1]

        # Fetch episodes
        episodes = []
        try:
            if any(domain in anime_url for domain in ["9animetv.to","anigo.to","hianime.to","aniwatchtv.to"]):
                scraper = CommonAnimeScraper()
                episodes = await scraper.get_episodes(anime_url)
            elif "gogoanime3.cv" in anime_url:
                episodes = await scrape_gogoanime(anime_url)
            elif "animixplay.by" in anime_url:
                episodes = await scrape_animixplay(anime_url)
            else:
                episodes = [{"title": "Download", "url": anime_url, "type": "link"}]

        except Exception as e:
            await q.edit_message_text(f"❌ Failed fetching episodes: {e}", parse_mode="Markdown")
            return

        if not episodes:
            await q.edit_message_text("⚠️ No episodes found.", parse_mode="Markdown")
            return

        context.user_data["pending_episodes"] = episodes
        context.user_data["quality_selected_event"] = asyncio.Event()

        kb = [[InlineKeyboardButton(opt, callback_data=f"qual_{opt.replace(' ','_')}")] for opt in QUALITY_OPTIONS]
        await q.edit_message_text("🎚 Select quality / sub or wait 5s for default (1080p sub):",
                                  reply_markup=InlineKeyboardMarkup(kb))

        try:
            await asyncio.wait_for(context.user_data["quality_selected_event"].wait(), timeout=5)
        except asyncio.TimeoutError:
            context.user_data["selected_quality"] = "1080p sub"
            context.user_data["quality_selected_event"].set()

    elif d.startswith("qual_"):
        selected_quality = d.split("_", 1)[1].replace("_"," ")
        context.user_data["selected_quality"] = selected_quality
        if "quality_selected_event" in context.user_data:
            context.user_data["quality_selected_event"].set()

        # Queue all episodes
        episodes = context.user_data.get("pending_episodes", [])
        quality = context.user_data.get("selected_quality", "1080p sub")
        await q.edit_message_text(f"⚡ Downloading all episodes ({quality})...")

        for ep in episodes:
            try:
                url = ep["url"]
                if "sub" in quality.lower():
                    url += "?sub=1"
                elif "dub" in quality.lower():
                    url += "?dub=1"

                gid = await downloader.add_torrent(url)
                if gid:
                    await monitor_and_process_download(gid, update, context, q.message)
            except Exception as e:
                logger.warning(f"Failed to queue episode {ep['title']}: {e}")

        # Cleanup
        context.user_data["pending_episodes"] = []
        context.user_data["selected_quality"] = None
        context.user_data.pop("quality_selected_event", None)

    elif d.startswith("cancel_"):
        gid = d.split("_", 1)[1]
        try:
            await downloader.remove_download(gid)
            await async_delete(f"./downloads/{gid}")
            await q.edit_message_text("🛑 **Stopped and cleaned.**", parse_mode="Markdown")

            context.user_data["pending_episodes"] = []
            context.user_data["selected_quality"] = None
            context.user_data.pop("quality_selected_event", None)

        except Exception as e:
            await q.edit_message_text(f"❌ Failed: {e}", parse_mode="Markdown")

# --- START MEMORY MANAGER ---
asyncio.get_event_loop().create_task(start_memory_manager())
