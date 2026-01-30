import gc
import os
import shutil
import asyncio
import logging
import time

logger = logging.getLogger(__name__)

class MemoryManager:
    def __init__(self, threshold_mb=400):
        # Trigger aggressive cleanup if RAM usage exceeds 400MB (limit is 512MB)
        self.threshold = threshold_mb * 1024 * 1024 
        self.running = False

    async def start(self):
        """Starts the background monitoring loop."""
        self.running = True
        logger.warning("🧠 Memory Manager Started")
        
        while self.running:
            try:
                self.check_memory()
                self.clean_stuck_downloads()
                # Run this check every 60 seconds
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Memory Manager Error: {e}")
                await asyncio.sleep(60)

    def check_memory(self):
        """Monitors RAM and forces Garbage Collection."""
        try:
            # We import psutil here (Lazy Import) so it's not constantly in memory if not needed
            import psutil
            process = psutil.Process(os.getpid())
            mem_usage = process.memory_info().rss
            
            # 1. Routine Cleanup: Tell Python to free up unused objects
            gc.collect()

            # 2. Emergency Cleanup: If we are close to the limit
            if mem_usage > self.threshold:
                logger.warning(f"⚠️ High RAM ({mem_usage / 1024 / 1024:.2f} MB). Force cleaning...")
                gc.collect(generation=2) # Aggressive collection
        except ImportError:
            # Fallback if psutil is missing
            gc.collect()

    def clean_stuck_downloads(self):
        """
        Deletes files in ./downloads that are older than 2 hours.
        This prevents 'Disk Full' errors if a download crashes halfway.
        """
        download_path = "./downloads"
        max_age = 2 * 60 * 60 # 2 Hours in seconds
        current_time = time.time()

        if os.path.exists(download_path):
            for f in os.listdir(download_path):
                f_path = os.path.join(download_path, f)
                try:
                    # Check file age
                    if os.stat(f_path).st_mtime < (current_time - max_age):
                        if os.path.isfile(f_path):
                            os.remove(f_path)
                        elif os.path.isdir(f_path):
                            shutil.rmtree(f_path)
                        logger.warning(f"♻️ Auto-Cleaned stuck file: {f}")
                except Exception:
                    pass

# Entry point for main.py
async def start_memory_manager():
    manager = MemoryManager()
    await manager.start()
