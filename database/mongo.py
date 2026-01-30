import motor.motor_asyncio
import re
import logging
import asyncio
from datetime import datetime
from functools import lru_cache
from config import Config

logger = logging.getLogger(__name__)

class MongoDB:
    def __init__(self):
        self.client = None
        self.db = None
        self.users = None
        self.history = None

        if not Config.MONGO_URL:
            logger.warning("MONGO_URL not found! DB features disabled.")
            return

        try:
            self.client = motor.motor_asyncio.AsyncIOMotorClient(
                Config.MONGO_URL,
                maxPoolSize=1,
                minPoolSize=0,
                serverSelectionTimeoutMS=5000
            )
            self.db = self.client[Config.DB_NAME]
            self.users = self.db.users
            self.history = self.db.history
            logger.info("✅ MongoDB client initialized.")
        except Exception as e:
            logger.error(f"Failed to connect MongoDB: {e}")
            self.db = None # Ensure it stays None on failure

    async def init_indexes(self):
        """Async-safe index creation with TTL cleanup"""
        # FIXED: Explicit check for None
        if self.db is None:
            return
        try:
            # Unique per user + anime
            await self.history.create_index(
                [("user_id", 1), ("anime", 1)], unique=True, background=True
            )
            # Optional TTL for auto cleanup: 30 days
            await self.history.create_index(
                [("last_updated", 1)],
                expireAfterSeconds=30*24*3600  # 30 days
            )
            logger.info("✅ MongoDB indexes created.")
        except Exception as e:
            logger.error(f"Failed to create indexes: {e}")

    # --- Connection Health ---
    async def ping(self):
        if self.client is None:
            return False
        try:
            await self.client.admin.command("ping")
            return True
        except:
            return False

    # --- Stats & Traffic ---
    async def get_total_users(self):
        if self.db is None: return 0
        return await self.users.count_documents({})

    async def get_total_traffic(self):
        if self.db is None: return 0, 0
        pipeline = [
            {"$group": {
                "_id": None,
                "total_down": {"$sum": "$downloaded"},
                "total_up": {"$sum": "$uploaded"}
            }}
        ]
        try:
            result = await self.users.aggregate(pipeline).to_list(length=1)
            if result:
                return result[0].get('total_down', 0), result[0].get('total_up', 0)
        except Exception as e:
            logger.error(f"Error fetching traffic: {e}")
        return 0, 0

    async def update_stats(self, user_id, bytes_downloaded=0, bytes_uploaded=0):
        if self.db is None: return
        await self.users.update_one(
            {"user_id": user_id},
            {
                "$inc": {"downloaded": bytes_downloaded, "uploaded": bytes_uploaded},
                "$setOnInsert": {"thumbnail": None}
            },
            upsert=True
        )

    # --- History & Episodes ---
    async def add_history(self, user_id, file_name):
        if self.db is None:
            return None, None

        # Supports "Anime - 12", "Anime.S01E12", "[Group] Anime - 12v2"
        match = re.search(
            r"(?:\[.*?\]\s*)?(.*?)\s*[-. ](?:S\d+E)?(\d+)",
            file_name, re.IGNORECASE
        )
        if match:
            anime_name = match.group(1).strip()
            episode = int(match.group(2))
            await self.history.update_one(
                {"user_id": user_id, "anime": anime_name},
                {"$set": {"last_ep": episode, "last_updated": datetime.utcnow()}},
                upsert=True
            )
            return anime_name, episode
        return None, None

    async def delete_history(self, user_id, anime_name):
        if self.db is None: return False
        try:
            await self.history.delete_one({"user_id": user_id, "anime": anime_name})
            return True
        except Exception as e:
            logger.error(f"Failed to delete history for {anime_name}: {e}")
            return False

    async def increment_episode(self, user_id, anime_name):
        if self.db is None: return
        await self.history.update_one(
            {"user_id": user_id, "anime": anime_name},
            {"$inc": {"last_ep": 1}, "$set": {"last_updated": datetime.utcnow()}},
            upsert=True
        )

    # --- Thumbnails with LRU Cache ---
    @lru_cache(maxsize=128)
    async def get_thumbnail(self, user_id):
        if self.db is None: return None
        user = await self.users.find_one({"user_id": user_id})
        return user.get("thumbnail") if user else None

    async def set_thumbnail(self, user_id, photo_binary):
        if self.db is None: return
        await self.users.update_one(
            {"user_id": user_id},
            {"$set": {"thumbnail": photo_binary}},
            upsert=True
        )

# --- CREATE SINGLETON INSTANCE ---
db = MongoDB()
