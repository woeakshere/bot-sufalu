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
        results = []

        try:
            async with get_safe_browser() as page:
                random.shuffle(self.sites)  # Avoid detection

                for site in self.sites:
                    try:
                        search_url = f"{site['url']}{site['search']}{query.replace(' ', '+')}"
                        logger.info(f"Searching {site['name']}...")

                        # Try navigating (retry once if blocked)
                        response = await page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
                        if response and response.status in [403, 503]:
                            await asyncio.sleep(random.uniform(1,2))
                            response = await page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
                            if response and response.status in [403, 503]:
                                logger.warning(f"{site['name']} blocked after retry. Skipping.")
                                continue

                        # Wait for results selector
                        try:
                            await page.wait_for_selector(site['selector'], timeout=4000)
                        except:
                            logger.debug(f"No results found on {site['name']}")
                            continue

                        elements = await page.query_selector_all(site['selector'])
                        for el in elements[:5]:  # Top 5 results per site
                            title_el = await el.query_selector(site['title'])
                            link_el = await el.query_selector("a")
                            if title_el and link_el:
                                title = await title_el.inner_text()
                                link = await link_el.get_attribute("href")
                                link = urljoin(site['url'], link)  # Ensure absolute URL
                                results.append({
                                    "title": f"[{site['name']}] {title.strip()}",
                                    "url": link,
                                    "type": "video"
                                })

                        if len(results) >= 5:
                            break  # Enough results, save resources

                    except Exception as e:
                        logger.error(f"Error scraping {site['name']}: {e}")
                        continue

        except Exception as e:
            logger.error(f"Critical scraper error: {e}")

        return results
