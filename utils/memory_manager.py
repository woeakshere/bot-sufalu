import gc
import os
import shutil
import asyncio
import logging
import time
import signal

logger = logging.getLogger(__name__)

class MemoryManager:
    def __init__(self):
        self.running = False
        
        # 🔒 HARDCODED SAFETY LIMITS (Crucial for Koyeb Free Tier)
        # We assume 512MB Total. We start cleaning at ~350MB to be safe.
        # If we rely on psutil.virtual_memory().total, it will report the SERVER'S 64GB RAM,
        # causing the bot to think it has infinite memory -> OOM Crash.
        self.total_mem_limit = 512 * 1024 * 1024
        
        # Thresholds:
        # Safe (70%): Trigger Python Garbage Collection
        self.safe_limit = self.total_mem_limit * 0.70     # ~358 MB
        
        # Critical (85%): Kill heavy sub-processes (Chrome/FFmpeg)
        self.critical_limit = self.total_mem_limit * 0.85 # ~435 MB
        
        logger.warning(f"🧠 Memory Governance: Active (Limit={self.total_mem_limit/1024**2:.0f}MB)")

    async def start(self):
        """Starts the background monitoring loop."""
        self.running = True
        while self.running:
            try:
                await self.health_check()
                # Check every 15s (Aggressive checks prevent OOM kills)
                await asyncio.sleep(15)
            except Exception as e:
                logger.error(f"Memory Loop Error: {e}")
                await asyncio.sleep(15)

    async def health_check(self):
        try:
            import psutil
            process = psutil.Process(os.getpid())
            mem_usage = process.memory_info().rss
            
            # 1. Light Cleanup (Always run if getting full)
            if mem_usage > self.safe_limit:
                gc.collect()

            # 2. Critical Cleanup (Kill Heavy Processes)
            # If we are close to the 512MB cliff, kill the heaviest process immediately.
            if mem_usage > self.critical_limit:
                logger.warning(f"🚨 RAM CRITICAL ({mem_usage/1024**2:.1f}MB)! Killing Chrome/FFmpeg...")
                self.kill_process_by_name("chrome")
                self.kill_process_by_name("ffmpeg")
                # Force a hard collection after killing
                gc.collect()
                
            # 3. Zombie Hunter (Stuck Scrapers)
            # Kill any chrome process older than 2 minutes (scrapers should be fast now)
            self.kill_zombies("chrome", max_age_seconds=120) 
            
            # 4. Disk Hygiene
            self.clean_stuck_downloads()

        except Exception as e:
            logger.error(f"Health Check Failed: {e}")

    def kill_process_by_name(self, name):
        """Kills any process matching the name (e.g., 'chrome')."""
        import psutil
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if name.lower() in proc.info['name'].lower():
                    proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    def kill_zombies(self, name, max_age_seconds):
        """Kills processes that have been running too long."""
        import psutil
        current_time = time.time()
        for proc in psutil.process_iter(['pid', 'name', 'create_time']):
            try:
                if name.lower() in proc.info['name'].lower():
                    if (current_time - proc.info['create_time']) > max_age_seconds:
                        logger.warning(f"🧟 Killed Zombie {name} (Running too long)")
                        proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    def clean_stuck_downloads(self):
        """Deletes files in ./downloads that are older than 3 hours."""
        download_path = "./downloads"
        if os.path.exists(download_path):
            current_time = time.time()
            for f in os.listdir(download_path):
                f_path = os.path.join(download_path, f)
                try:
                    # Delete files older than 3 hours (10800 seconds)
                    if os.stat(f_path).st_mtime < (current_time - 10800):
                        if os.path.isfile(f_path): os.remove(f_path)
                        elif os.path.isdir(f_path): shutil.rmtree(f_path)
                        logger.warning(f"♻️ Cleaned junk: {f}")
                except Exception:
                    pass

# Entry point
async def start_memory_manager():
    manager = MemoryManager()
    await manager.start()
