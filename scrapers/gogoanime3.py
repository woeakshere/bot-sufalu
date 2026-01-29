import asyncio
from utils.safe_browser import get_safe_browser

async def scrape_gogoanime(query):
    try:
        async with get_safe_browser() as page:
            url = f"https://gogoanime3.cv/search.html?keyword={query.replace(' ', '%20')}"
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            results = []
            try:
                await page.wait_for_selector(".items li", timeout=10000)
                anime_elements = await page.query_selector_all(".items li")
                
                for element in anime_elements:
                    title_el = await element.query_selector(".name a")
                    link_el = await element.query_selector("a")
                    
                    if title_el and link_el:
                        title = await title_el.inner_text()
                        link = await link_el.get_attribute("href")
                        if link.startswith("/"):
                            link = f"https://gogoanime3.cv{link}"
                        
                        # --- PRESET CONFIGURATION ---
                        result_type = "video" # Default: Quality Menu
                        # result_type = "link" # Uncomment for Direct Link Bypass
                        
                        results.append({
                            "title": title.strip(), 
                            "url": link,
                            "type": result_type
                        })
            except Exception:
                pass
            
            return results
    except Exception as e:
        print(f"Gogoanime Error: {e}")
        return []