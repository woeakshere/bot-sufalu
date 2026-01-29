import motor.motor_asyncio
import re
import logging
from config import Config

logger = logging.getLogger(__name__)

class MongoDB:
    def __init__(self):
        if not Config.MONGO_URL:
            logger.warning("MONGO_URL not found! Database features will be disabled.")
            self.client = None
            self.db = None
            return

        try:
            self.client = motor.motor_asyncio.AsyncIOMotorClient(Config.MONGO_URL)
            self.db = self.client[Config.DB_NAME]
            
            # Collections
            self.users = self.db.users
            self.history = self.db.history

            # OPTIMIZATION: Create Index for fast lookups
            self.history.create_index([("user_id", 1), ("anime", 1)], unique=True, background=True)
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            self.client = None
            self.db = None

    # --- STATS & TRAFFIC ---

    async def get_total_users(self):
        if not self.db: return 0
        return await self.users.count_documents({})

    async def get_total_traffic(self):
        if not self.db: return 0, 0
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
                return result[0]['total_down'], result[0]['total_up']
        except:
            pass
        return 0, 0

    async def update_stats(self, user_id, bytes_downloaded=0, bytes_uploaded=0):
        if not self.db: return
        await self.users.update_one(
            {"user_id": user_id},
            {"$inc": {"downloaded": bytes_downloaded, "uploaded": bytes_uploaded}},
            upsert=True
        )

    # --- WATCH HISTORY & NEXT EPISODE ---

    async def add_history(self, user_id, file_name):
        if not self.db: return None, None
        match = re.search(r"(?:\[.*?\]\s*)?(.*?)\s*-\s*(\d+)", file_name)
        if match:
            anime_name = match.group(1).strip()
            episode = int(match.group(2))
            await self.history.update_one(
                {"user_id": user_id, "anime": anime_name},
                {"$set": {"last_ep": episode}},
                upsert=True
            )
            return anime_name, episode
        return None, None

    async def delete_history(self, user_id, anime_name):
        if not self.db: return False
        try:
            await self.history.delete_one({"user_id": user_id, "anime": anime_name})
            return True
        except Exception as e:
            logger.error(f"Failed to delete history for {anime_name}: {e}")
            return False

# Create a single instance to be imported elsewhere
db = MongoDB()
