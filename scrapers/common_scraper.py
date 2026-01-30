import asyncio
import random
import logging
from utils.safe_browser import get_safe_browser

logger = logging.getLogger(__name__)

class CommonAnimeScraper:
    def __init__(self):
        # We don't need to set a user_agent here anymore; SafeBrowser handles it globally.
        self.sites = [
            # 9Anime / AniWave
            {
                "name": "9Anime", 
                "url": "https://9animetv.to", 
                "search": "/search?keyword=", 
                "selector": ".film-list .item", 
                "title": ".name"
            },
            # AniGo
            {
                "name": "AniGo", 
                "url": "https://anigo.to", 
                "search": "/browser?keyword=", 
                "selector": ".anime-list .item", 
                "title": ".name"
            },
            # HiAnime (Rebranded Aniwatch)
            {
                "name": "Hianime", 
                "url": "https://hianime.to", 
                "search": "/search?keyword=", 
                "selector": ".film_list-wrap .flw-item", 
                "title": ".film-name a"
            },
            # Aniwatch (Legacy/Mirror)
            {
                "name": "Aniwatch", 
                "url": "https://aniwatchtv.to", 
                "search": "/search?keyword=", 
                "selector": ".film_list-wrap .flw-item", 
                "title": ".film-name a"
            }
        ]

    async def run(self, query):
        """
        Runs the scraper using the centralized SafeBrowser.
        This automatically gains:
        - Ad Blocking (Speedup)
        - Stealth Mode (Bypass Cloudflare)
        - Docker Flags (Prevent Crashes)
        """
        results = []
        
        # 1. Initialize the Safe Browser (Same as Gogo/AllAnime)
        try:
            async with get_safe_browser() as page:
                
                # Randomize site order to avoid pattern detection
                random.shuffle(self.sites) 
                
                for site in self.sites:
                    try:
                        search_url = f"{site['url']}{site['search']}{query.replace(' ', '+')}"
                        logger.info(f"Searching: {site['name']}...")

                        # 2. Navigate with Safety
                        # 'domcontentloaded' is faster than 'networkidle' and safer with ad-blockers
                        response = await page.goto(search_url, wait_until="domcontentloaded", timeout=15000)
                        
                        # Check for soft-bans (Cloudflare or 403)
                        if response and response.status in [403, 503]:
                            logger.warning(f"{site['name']} blocked (Status {response.status}). Skipping.")
                            continue

                        # 3. Wait for Content (Robust Check)
                        try:
                            await page.wait_for_selector(site['selector'], timeout=4000)
                        except:
                            logger.debug(f"No results or timeout on {site['name']}")
                            continue 

                        # 4. Extract Data
                        elements = await page.query_selector_all(site['selector'])
                        
                        for el in elements[:5]: # Limit to top 5 per site
                            title_el = await el.query_selector(site['title'])
                            link_el = await el.query_selector("a")
                            
                            if title_el and link_el:
                                title = await title_el.inner_text()
                                link = await link_el.get_attribute("href")
                                
                                # Fix relative URLs
                                if link.startswith("/"):
                                    link = f"{site['url']}{link}"
                                
                                results.append({
                                    "title": f"[{site['name']}] {title.strip()}", 
                                    "url": link,
                                    "type": "video" # Default type for handlers.py
                                })
                        
                        # Optimization: If we found good results, we can stop early 
                        # to save resources, or keep going to gather more.
                        if len(results) >= 5: 
                            break 

                    except Exception as e:
                        logger.error(f"Error scraping {site['name']}: {e}")
                        continue

        except Exception as e:
            logger.error(f"Critical Scraper Error: {e}")

        return results
