import motor.motor_asyncio
import re
import logging
from config import Config

logger = logging.getLogger(__name__)

class MongoDB:
    def __init__(self):
        # 1. Check if URL is provided
        if not Config.MONGO_URL:
            logger.warning("MONGO_URL not found! Database features will be disabled.")
            self.client = None
            self.db = None
            return

        try:
            # 2. Initialize Connection
            self.client = motor.motor_asyncio.AsyncIOMotorClient(Config.MONGO_URL)
            self.db = self.client[Config.DB_NAME]
            
            # 3. Define Collections
            self.users = self.db.users
            self.history = self.db.history

            # 4. Create Index (Critical for speed)
            # Ensures searching for "One Piece" is instant
            self.history.create_index([("user_id", 1), ("anime", 1)], unique=True, background=True)
            logger.info("✅ Connected to MongoDB successfully.")
            
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            self.client = None
            self.db = None

    # --- STATS & TRAFFIC ---

    async def get_total_users(self):
        """Returns the number of unique users using the bot."""
        # FIX: Check explicitly for None
        if self.db is None: 
            return 0
        return await self.users.count_documents({})

    async def get_total_traffic(self):
        """Calculates total Download/Upload bytes across all users."""
        if self.db is None: 
            return 0, 0
            
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
        except Exception as e:
            logger.error(f"Error fetching traffic stats: {e}")
        return 0, 0

    async def update_stats(self, user_id, bytes_downloaded=0, bytes_uploaded=0):
        """Updates traffic stats for a specific user."""
        if self.db is None: 
            return
            
        await self.users.update_one(
            {"user_id": user_id},
            {"$inc": {"downloaded": bytes_downloaded, "uploaded": bytes_uploaded}},
            upsert=True
        )

    # --- WATCH HISTORY & NEXT EPISODE ---

    async def add_history(self, user_id, file_name):
        """
        Parses filename to extract Anime Name & Episode Number.
        Updates DB and returns the parsed info.
        """
        if self.db is None: 
            return None, None
            
        # Regex to find "Anime Name - 12" pattern
        # Handles "[Group] Anime - 12 [1080p].mkv"
        match = re.search(r"(?:\[.*?\]\s*)?(.*?)\s*-\s*(\d+)", file_name)
        
        if match:
            anime_name = match.group(1).strip()
            episode = int(match.group(2))
            
            # Upsert: Create if doesn't exist, Update if it does
            await self.history.update_one(
                {"user_id": user_id, "anime": anime_name},
                {"$set": {"last_ep": episode}},
                upsert=True
            )
            return anime_name, episode
            
        return None, None

    async def delete_history(self, user_id, anime_name):
        """
        Deletes a specific anime from history.
        Used for the 'Auto-Cleanup' feature.
        """
        if self.db is None: 
            return False
            
        try:
            await self.history.delete_one({"user_id": user_id, "anime": anime_name})
            return True
        except Exception as e:
            logger.error(f"Failed to delete history for {anime_name}: {e}")
            return False

# Create the instance
db = MongoDB()
