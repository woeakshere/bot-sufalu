import asyncio
import random
# Import the new safe browser utility
from utils.safe_browser import get_safe_browser

class AnimeBot:
    def __init__(self):
        self.sites = [
            {"name": "AllAnime", "search_url": "https://allanime.to/search?q="},
        ]

    async def get_search_results(self, page, site, query):
        """Standardizes search result extraction across different sites."""
        url = f"{site['search_url']}{query.replace(' ', '+')}"
        
        # SafeBrowser handles ad-blocking, so domcontentloaded is usually safe and faster
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        
        results = []
        try:
            # Wait for either class commonly used in these site templates
            await page.wait_for_selector(".anime-list, .item", timeout=10000)
            elements = await page.query_selector_all(".anime-list .item, .item")
            
            for el in elements:
                title_el = await el.query_selector(".name, .title")
                link_el = await el.query_selector("a")
                
                if title_el and link_el:
                    title = await title_el.inner_text()
                    link = await link_el.get_attribute("href")
                    
                    if link.startswith("/"):
                        base = "https://allanime.to" # Hardcoded base for reliability
                        link = f"{base}{link}"
                    
                    # --- PRESET CONFIGURATION ---
                    # AllAnime is typically a 'Direct Link' type source
                    # handlers.py uses this 'type' to send the link directly to channel
                    results.append({
                        "title": title.strip(), 
                        "url": link,
                        "type": "link" # Triggers the 'lnk_' preset in handlers.py
                    })
        except Exception as e:
            print(f"Error scraping {site['name']}: {e}")
            
        return results

    async def run(self, query):
        """
        Executes search using the centralized SafeBrowser.
        """
        # Replaces manual Playwright setup with the intelligent context manager
        async with get_safe_browser() as page:
            all_results = []
            for site in self.sites:
                try:
                    results = await self.get_search_results(page, site, query)
                    all_results.extend(results)
                except Exception as e:
                    print(f"Error on {site['name']}: {e}")
                    continue
            
            return all_results