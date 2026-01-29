import aria2p
import os
import asyncio
from config import Config

class TorrentDownloader:
    def __init__(self):
        self.aria2 = aria2p.API(
            aria2p.Client(
                host="http://localhost",
                port=6800,
                secret=""
            )
        )

    async def add_torrent(self, magnet_or_link):
        try:
            download = self.aria2.add_magnet(magnet_or_link)
            return download.gid
        except Exception as e:
            print(f"Error adding torrent: {e}")
            return None

    async def get_status(self, gid):
        try:
            download = self.aria2.get_download(gid)
            return {
                "name": download.name,
                "progress": download.progress,
                "size": download.total_length_string(),
                "speed": download.download_speed_string(),
                "status": download.status
            }
        except Exception as e:
            print(f"Error getting status: {e}")
            return None

    async def wait_for_completion(self, gid, callback=None):
        while True:
            status = await self.get_status(gid)
            if not status:
                break
            
            if callback:
                await callback(status)
            
            if status["status"] == "complete":
                break
            elif status["status"] == "error":
                print("Download failed")
                break
            
            await asyncio.sleep(5)
