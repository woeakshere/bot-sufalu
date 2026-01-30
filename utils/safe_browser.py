import asyncio
import time
import random
import logging
from contextlib import asynccontextmanager
from playwright.async_api import async_playwright, Page, BrowserContext

logger = logging.getLogger(__name__)

# =========================
# AUTOPILOT CONFIG (HIDDEN)
# =========================

BLOCKED_RESOURCES = {
    "image", "font", "media", "websocket", "manifest", "texttrack"
}

AD_KEYWORDS = (
    "ads", "doubleclick", "tracking", "analytics", "pixel",
    "bet", "casino", "promo", "offer", "bonus", "profit",
    "dating", "adult", "click", "pop", "redirect"
)

TRUSTED_HOSTS = (
    "gofile", "pixeldrain", "krakenfiles", "mega",
    "filemoon", "dood", "streamtape", "sendcm",
    "mp4upload", "vidstream", "gogoanime", "allanime"
)

MAX_BROWSER_LIFETIME = 10 * 60   # recycle every 10 min
MAX_PAGES_PER_CONTEXT = 5

# =========================
# AUTOPILOT SAFE BROWSER
# =========================

class SafeBrowser:
    """
    Fully automated, admin-proof, self-healing browser.
    Usage stays IDENTICAL.
    """

    def __init__(self, headless=True):
        self.headless = headless
        self._started_at = time.time()
        self._page_count = 0

        self.playwright = None
        self.browser = None
        self.context = None

    # -------------------------
    # Context Manager
    # -------------------------

    async def __aenter__(self) -> Page:
        await self._boot()
        page = await self._new_page()
        return page

    async def __aexit__(self, exc_type, exc, tb):
        await self._cleanup()

    # -------------------------
    # Boot Sequence
    # -------------------------

    async def _boot(self):
        self.playwright = await async_playwright().start()

        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--mute-audio",
                "--disable-infobars"
            ]
        )

        self.context = await self.browser.new_context(
            user_agent=self._random_ua(),
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            timezone_id="America/New_York",
            java_script_enabled=True,
        )

        await self._stealth(self.context)
        await self._blockers(self.context)
        await self._popup_guard(self.context)
        await self._auto_consent(self.context)

    # -------------------------
    # Page Handling
    # -------------------------

    async def _new_page(self) -> Page:
        self._page_count += 1

        if self._should_recycle():
            await self._recycle()

        page = await self.context.new_page()
        page.set_default_timeout(25_000)

        await self._humanize(page)
        return page

    def _should_recycle(self):
        return (
            self._page_count >= MAX_PAGES_PER_CONTEXT or
            time.time() - self._started_at > MAX_BROWSER_LIFETIME
        )

    async def _recycle(self):
        logger.warning("♻️ Recycling browser context (RAM safety)")
        await self._cleanup()
        self.__init__(self.headless)
        await self._boot()

    # -------------------------
    # Network Control
    # -------------------------

    async def _blockers(self, context: BrowserContext):
        async def route(route):
            req = route.request
            url = req.url.lower()

            if req.resource_type in BLOCKED_RESOURCES:
                return await route.abort()

            if any(k in url for k in AD_KEYWORDS):
                return await route.abort()

            await route.continue_()

        await context.route("**/*", route)

    async def _popup_guard(self, context: BrowserContext):
        async def on_page(page: Page):
            try:
                await page.wait_for_load_state("domcontentloaded", timeout=3000)
                url = page.url.lower()

                if any(h in url for h in TRUSTED_HOSTS):
                    return

                if url == "about:blank" or any(k in url for k in AD_KEYWORDS):
                    await page.close()

            except Exception:
                if not page.is_closed():
                    await page.close()

        context.on("page", on_page)

    # -------------------------
    # Stealth & Humanization
    # -------------------------

    async def _stealth(self, context: BrowserContext):
        scripts = [
            "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})",
            "window.chrome={runtime:{}}",
            "Object.defineProperty(navigator,'languages',{get:()=>['en-US','en']})",
            "Object.defineProperty(navigator,'plugins',{get:()=>[1,2,3,4,5]})"
        ]
        for s in scripts:
            await context.add_init_script(s)

    async def _humanize(self, page: Page):
        await page.add_init_script(
            f"""
            (() => {{
                const delay = ms => new Promise(r => setTimeout(r, ms));
                document.addEventListener('click', async () => {{
                    await delay({random.randint(30,80)});
                }});
            }})();
            """
        )

    async def _auto_consent(self, context: BrowserContext):
        await context.add_init_script("""
            setInterval(() => {
                const words = ['accept','agree','consent','allow'];
                document.querySelectorAll('button').forEach(b=>{
                    const t=(b.innerText||'').toLowerCase();
                    if(words.some(w=>t.includes(w)) && t.length<20) b.click();
                });
            }, 1200);
        """)

    # -------------------------
    # Cleanup
    # -------------------------

    async def _cleanup(self):
        try:
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception:
            pass

    # -------------------------
    # Utils
    # -------------------------

    def _random_ua(self):
        return random.choice([
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/119.0.0.0",
        ])


# =========================
# PUBLIC ENTRY (UNCHANGED)
# =========================

def get_safe_browser():
    return SafeBrowser()
