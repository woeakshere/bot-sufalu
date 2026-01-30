# animixplay.py
import asyncio
from utils.safe_browser import get_safe_browser

async def scrape_animixplay(query):
    """Search AnimixPlay and return top anime results."""
    try:
        async with get_safe_browser() as page:
            search_url = f"https://animixplay.by/?s={query.replace(' ', '+')}"
            await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
            
            results = []
            try:
                await page.wait_for_selector(".result-item, .item", timeout=10000)
                elements = await page.query_selector_all(".result-item, .item")
                
                for element in elements[:10]:  # Top 10 results
                    title_el = await element.query_selector(".title, .name")
                    link_el = await element.query_selector("a")
                    
                    if title_el and link_el:
                        title = await title_el.inner_text()
                        link = await link_el.get_attribute("href")
                        
                        if link.startswith("/"):
                            link = f"https://animixplay.by{link}"
                        
                        results.append({
                            "title": f"[AniMix] {title.strip()}",
                            "url": link,
                            "type": "video"  # Indicates episode page
                        })
            except Exception:
                pass
            
            return results
    except Exception as e:
        print(f"AniMixPlay Search Error: {e}")
        return []


# --- Extract episodes for selected anime ---
async def get_animixplay_episodes(anime_url):
    """
    Given an anime page, return a list of episodes with URLs.
    """
    try:
        async with get_safe_browser() as page:
            await page.goto(anime_url, wait_until="domcontentloaded", timeout=60000)
            
            # AnimixPlay uses a "Play" button / episode list
            await page.wait_for_selector(".episodes a, .episode-list a", timeout=10000)
            ep_elements = await page.query_selector_all(".episodes a, .episode-list a")
            
            episodes = []
            for ep in ep_elements:
                ep_title = await ep.inner_text()
                ep_link = await ep.get_attribute("href")
                
                if ep_link.startswith("/"):
                    ep_link = f"https://animixplay.by{ep_link}"
                
                episodes.append({
                    "title": ep_title.strip(),
                    "url": ep_link,
                    "type": "video"
                })
            
            # Sort episodes numerically if possible
            def ep_key(e):
                import re
                match = re.search(r"\d+", e["title"])
                return int(match.group()) if match else 0
            episodes.sort(key=ep_key)
            
            return episodes
    except Exception as e:
        print(f"AniMixPlay Episode Extraction Error: {e}")
        return []
