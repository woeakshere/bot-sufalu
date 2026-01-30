# common_scraper.py
import asyncio
import random
import logging
from urllib.parse import urljoin
from utils.safe_browser import get_safe_browser

logger = logging.getLogger(__name__)

class CommonAnimeScraper:
    """
    Centralized scraper for multiple anime sites using SafeBrowser:
    - Ad & popup blocking
    - Stealth mode (Cloudflare bypass)
    - Automatic retries for blocked sites
    - Returns top 5 results per query
    """

    def __init__(self):
        self.sites = [
            {"name": "9Anime", "url": "https://9animetv.to", "search": "/search?keyword=", "selector": ".film-list .item", "title": ".name"},
            {"name": "AniGo", "url": "https://anigo.to", "search": "/browser?keyword=", "selector": ".anime-list .item", "title": ".name"},
            {"name": "Hianime", "url": "https://hianime.to", "search": "/search?keyword=", "selector": ".film_list-wrap .flw-item", "title": ".film-name a"},
            {"name": "Aniwatch", "url": "https://aniwatchtv.to", "search": "/search?keyword=", "selector": ".film_list-wrap .flw-item", "title": ".film-name a"}
        ]

    async def run(self, query: str):
        """
        Search for anime by query.
        Returns top 5 results per site.
        """
        results = []

        try:
            async with get_safe_browser() as page:
                random.shuffle(self.sites)  # Avoid detection

                for site in self.sites:
                    try:
                        search_url = f"{site['url']}{site['search']}{query.replace(' ', '+')}"
                        logger.info(f"Searching {site['name']}: {search_url}")

                        response = await page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
                        if response and response.status in [403, 503]:
                            logger.warning(f"{site['name']} blocked (Status {response.status})")
                            continue

                        # Wait for results
                        try:
                            await page.wait_for_selector(site['selector'], timeout=5000)
                        except:
                            logger.debug(f"No results on {site['name']}")
                            continue

                        elements = await page.query_selector_all(site['selector'])
                        for el in elements[:5]:  # top 5 per site
                            title_el = await el.query_selector(site['title'])
                            link_el = await el.query_selector("a")

                            if title_el and link_el:
                                title = await title_el.inner_text()
                                link = await link_el.get_attribute("href")
                                if link.startswith("/"):
                                    link = urljoin(site['url'], link)

                                results.append({
                                    "title": f"[{site['name']}] {title.strip()}",
                                    "url": link,
                                    "type": "video"  # triggers episode fetch in handlers
                                })

                        # Stop early if enough results
                        if len(results) >= 5:
                            break

                    except Exception as e:
                        logger.error(f"Error scraping {site['name']}: {e}")
                        continue

        except Exception as e:
            logger.error(f"Critical Scraper Error: {e}")

        return results

    async def get_episodes(self, anime_url: str):
        """
        Fetch all episodes from a given anime page URL.
        Returns a list of dicts: [{title, url, type='video'}]
        """
        episodes = []
        try:
            async with get_safe_browser() as page:
                await page.goto(anime_url, wait_until="domcontentloaded", timeout=20000)

                # Try common episode selectors
                selectors = [
                    ".episode_list li a",       # 9Anime
                    ".listing li a",            # AniGo
                    ".film-list .episode a",    # Hianime / Aniwatch
                    ".episodes a"
                ]
                ep_links = []
                for sel in selectors:
                    try:
                        await page.wait_for_selector(sel, timeout=5000)
                        ep_links = await page.query_selector_all(sel)
                        if ep_links:
                            break
                    except:
                        continue

                for el in ep_links:
                    title = await el.inner_text()
                    link = await el.get_attribute("href")
                    if link.startswith("/"):
                        link = urljoin(anime_url, link)

                    episodes.append({
                        "title": title.strip(),
                        "url": link,
                        "type": "video"
                    })

        except Exception as e:
            logger.error(f"Failed fetching episodes from {anime_url}: {e}")

        return episodes
