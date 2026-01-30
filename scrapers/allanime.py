# intelligent_scraper.py
import asyncio
import logging
from utils.safe_browser import get_safe_browser

logger = logging.getLogger(__name__)

TRUSTED_HOSTS = [
    "mega.nz", "mediafire.com", "gofile.io", "pixeldrain.com",
    "send.cm", "1fichier.com", "streamtape.com", "dood.to",
    "filemoon.com", "mp4upload.com"
]

class IntelligentScraper:
    def __init__(self, sites=None):
        # List of anime search sites
        self.sites = sites or [
            {"name": "AllAnime", "search_url": "https://allanime.to/search?q="},
            {"name": "GogoAnime", "search_url": "https://www3.gogoanime.pe//search.html?keyword="},
        ]

    async def search(self, query, top_n=5):
        """Return top search results for the query."""
        async with get_safe_browser() as page:
            results = []
            for site in self.sites:
                try:
                    search_url = f"{site['search_url']}{query.replace(' ', '+')}"
                    await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(1)

                    # Find clickable items for anime results
                    candidates = await page.query_selector_all("a, .item, .film-name, .name")
                    for el in candidates[:top_n]:
                        title = await el.inner_text()
                        link = await el.get_attribute("href")
                        if link.startswith("/"):
                            base = site['search_url'].split("/search")[0]
                            link = f"{base}{link}"
                        results.append({"title": f"[{site['name']}] {title.strip()}", "url": link})
                except Exception as e:
                    logger.warning(f"Search failed on {site['name']}: {e}")
            return results

    async def resolve_download(self, anime_page_url, max_clicks=10):
        """
        Opens the anime page and intelligently clicks buttons
        until a trusted download link is found.
        """
        async with get_safe_browser() as page:
            try:
                await page.goto(anime_page_url, wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(1)

                candidates = await page.query_selector_all("a, button")
                for idx, el in enumerate(candidates[:max_clicks]):
                    try:
                        await el.scroll_into_view_if_needed()
                        await el.click()
                        await asyncio.sleep(2)

                        # Check main page URL
                        url = page.url.lower()
                        if any(host in url for host in TRUSTED_HOSTS):
                            return url

                        # Check all open pages (popups)
                        for p in page.context.pages:
                            p_url = p.url.lower()
                            if any(host in p_url for host in TRUSTED_HOSTS):
                                return p_url
                    except:
                        continue
                return None
            except Exception as e:
                logger.error(f"Download resolution failed: {e}")
                return None
