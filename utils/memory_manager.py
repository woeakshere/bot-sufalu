import gc
import os
import shutil
import asyncio
import logging
import time
import signal

logger = logging.getLogger(__name__)

class MemoryManager:
    def __init__(self, safe_limit_percent=85, critical_limit_percent=95):
        self.running = False
        
        # Lazy load psutil to get system stats immediately
        import psutil
        total_mem = psutil.virtual_memory().total
        
        # Calculate thresholds dynamically based on real container size
        self.safe_limit = total_mem * (safe_limit_percent / 100)
        self.critical_limit = total_mem * (critical_limit_percent / 100)
        
        logger.warning(f"🧠 Memory Manager Initialized: Limit={self.safe_limit / 1024**2:.0f}MB")

    async def start(self):
        """Starts the background monitoring loop."""
        self.running = True
        logger.info("🧠 Memory Monitor Active")
        
        while self.running:
            try:
                await self.health_check()
                # Run checks every 30 seconds (More frequent = Safer)
                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"Memory Loop Error: {e}")
                await asyncio.sleep(30)

    async def health_check(self):
        """Performs graduated cleanup based on severity."""
        try:
            import psutil
            process = psutil.Process(os.getpid())
            mem_usage = process.memory_info().rss
            
            # LEVEL 1: Routine Maintenance (Always Run)
            gc.collect()

            # LEVEL 2: Warning Zone (Usage > 85%)
            if mem_usage > self.safe_limit:
                logger.warning(f"⚠️ High RAM ({mem_usage / 1024**2:.1f}MB). Aggressive GC...")
                gc.collect(generation=2) 
                
            # LEVEL 3: CRITICAL ZONE (Usage > 95%) - THE NUCLEAR OPTION
            if mem_usage > self.critical_limit:
                logger.error("🚨 CRITICAL MEMORY! KILLING BROWSERS & ENCODERS...")
                self.kill_process_by_name("chrome")
                self.kill_process_by_name("ffmpeg")
                self.kill_process_by_name("aria2c") # Last resort: Restart Aria2
                
            # LEVEL 4: Cleanup Stuck Scrapers (Zombie Hunter)
            # Kills any 'chrome' process older than 5 minutes (Scrapers shouldn't run that long)
            self.kill_zombies("chrome", max_age_seconds=300) 
            
            # LEVEL 5: Disk Hygiene
            self.clean_stuck_downloads()

        except ImportError:
            pass # psutil missing
        except Exception as e:
            logger.error(f"Health Check Failed: {e}")

    def kill_process_by_name(self, name):
        """Force kills all processes with a specific name."""
        import psutil
        count = 0
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if name.lower() in proc.info['name'].lower():
                    proc.kill()
                    count += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if count > 0:
            logger.warning(f"🔪 Killed {count} '{name}' processes to free RAM.")

    def kill_zombies(self, name, max_age_seconds):
        """Kills specific processes that have been running too long (Stuck)."""
        import psutil
        current_time = time.time()
        for proc in psutil.process_iter(['pid', 'name', 'create_time']):
            try:
                if name.lower() in proc.info['name'].lower():
                    runtime = current_time - proc.info['create_time']
                    if runtime > max_age_seconds:
                        logger.warning(f"🧟 Killed Zombie '{name}' (Running for {int(runtime)}s)")
                        proc.kill()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    def clean_stuck_downloads(self):
        """Deletes files in ./downloads that are older than 2 hours."""
        download_path = "./downloads"
        max_age = 2 * 60 * 60 
        current_time = time.time()

        if os.path.exists(download_path):
            for f in os.listdir(download_path):
                f_path = os.path.join(download_path, f)
                try:
                    # Check if file is modified recently (Active download?)
                    # If last modified > 2 hours ago, it's definitely stuck.
                    if os.stat(f_path).st_mtime < (current_time - max_age):
                        if os.path.isfile(f_path): os.remove(f_path)
                        elif os.path.isdir(f_path): shutil.rmtree(f_path)
                        logger.warning(f"♻️ Cleaned junk: {f}")
                except Exception:
                    pass

# Entry point
async def start_memory_manager():
    manager = MemoryManager()
    await manager.start()
