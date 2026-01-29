import asyncio
from utils.safe_browser import get_safe_browser

async def scrape_animixplay(query):
    try:
        async with get_safe_browser() as page:
            search_url = f"https://animixplay.by/?s={query.replace(' ', '+')}"
            await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
            
            results = []
            try:
                await page.wait_for_selector(".result-item, .item", timeout=10000)
                elements = await page.query_selector_all(".result-item, .item")
                
                for element in elements:
                    title_el = await element.query_selector(".title, .name")
                    link_el = await element.query_selector("a")
                    
                    if title_el and link_el:
                        title = await title_el.inner_text()
                        link = await link_el.get_attribute("href")
                        
                        if link.startswith("/"):
                            link = f"https://animixplay.by{link}"
                        
                        # --- PRESET CONFIGURATION ---
                        result_type = "video" # Default: Quality Menu
                        # result_type = "link" # Uncomment for Direct Link Bypass
                        
                        results.append({
                            "title": f"[AniMix] {title.strip()}",
                            "url": link,
                            "type": result_type
                        })
            except Exception:
                pass
            
            return results
    except Exception as e:
        print(f"AniMixPlay Error: {e}")
        return []