import asyncio
import random
from playwright.async_api import async_playwright

class CommonAnimeScraper:
    def __init__(self):
        self.user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        # Consolidated site configurations from your files
        self.sites = [
            {"name": "9Anime", "url": "https://9animetv.to", "search": "/search?keyword=", "selector": ".film-list .item", "title": ".name"},
            {"name": "AniGo", "url": "https://anigo.to", "search": "/browser?keyword=", "selector": ".anime-list .item", "title": ".name"},
            {"name": "Aniwatch", "url": "https://aniwatchtv.to", "search": "/search?keyword=", "selector": ".film_list-wrap .flw-item", "title": ".film-name a"},
            {"name": "Hianime", "url": "https://hianime.to", "search": "/search?keyword=", "selector": ".film_list-wrap .flw-item", "title": ".film-name a"}
        ]

    async def run(self, query):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=self.user_agent)
            page = await context.new_page()

            random.shuffle(self.sites) # Rotate to avoid hitting one site too hard
            all_results = []
            
            for site in self.sites:
                try:
                    search_url = f"{site['url']}{site['search']}{query.replace(' ', '+')}"
                    await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                    
                    await page.wait_for_selector(site['selector'], timeout=5000)
                    elements = await page.query_selector_all(site['selector'])
                    
                    for el in elements[:5]: # Top 5 results per site
                        title_el = await el.query_selector(site['title'])
                        link_el = await el.query_selector("a")
                        
                        if title_el and link_el:
                            title = await title_el.inner_text()
                            link = await link_el.get_attribute("href")
                            if link.startswith("/"):
                                link = f"{site['url']}{link}"
                            all_results.append({"title": f"[{site['name']}] {title.strip()}", "url": link})
                    
                    if all_results: break # Stop once we have successful results
                except:
                    continue # Try next site if this one fails

            await browser.close()
            return all_results
