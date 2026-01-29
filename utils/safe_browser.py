import asyncio
from playwright.async_api import async_playwright, Page, BrowserContext

# --- CONFIGURATION ---

# Resources to block for faster loading and bandwidth saving
BLOCKED_RESOURCES = [
    "image", "font", "media", "websocket", "other", "manifest", "texttrack"
]

# Keywords in URL/Title that indicate an Ad, Tracker, or Spam tab
AD_KEYWORDS = [
    "betting", "casino", "poker", "dating", "adult", "click", 
    "tracker", "analytics", "pixel", "adsystem", "syndication",
    "doubleclick", "pop", "cash", "crypto", "forex", "profit", 
    "revenue", "offer", "bonus", "game"
]

# Trusted File Hosts (Allow redirects to these domains for downloading)
# Add any new hosts your scrapers use here.
TRUSTED_FILE_HOSTS = [
    "gofile", "krakenfiles", "mega.nz", "pixeldrain", "sendcm", 
    "1fichier", "mediafire", "streamtape", "mp4upload", "dood", 
    "filemoon", "vidstream", "allanime", "gogoanime", "animixplay"
]

class SafeBrowser:
    """
    A robust browser context manager that handles:
    1. Stealth Mode (Bypasses bot detection)
    2. Ad & Resource Blocking (Speed & Safety)
    3. Smart Popup Killing (Closes ads, allows file hosts)
    4. Auto-Cookie Consent (Clicks 'Accept' automatically)
    5. Aggressive Cleanup (Wipes cache/workers on exit)
    """
    def __init__(self, headless=True):
        self.headless = headless
        self.playwright = None
        self.browser = None
        self.context = None

    async def __aenter__(self) -> Page:
        self.playwright = await async_playwright().start()
        
        # Launch Chromium with anti-detection arguments
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--disable-gpu",
                "--window-size=1920,1080",
                "--mute-audio" # Mute any auto-playing video ads
            ]
        )
        
        # Create a persistent context structure (isolated session)
        self.context = await self.browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='America/New_York',
            device_scale_factor=1,
            has_touch=False,
            java_script_enabled=True,
        )

        # 1. Activate Ad & Resource Blocker
        await self._activate_ad_blocker(self.context)
        
        # 2. Activate Smart Popup Killer
        await self._activate_smart_popup_killer(self.context)
        
        # 3. Apply Advanced Stealth Scripts
        await self._apply_advanced_stealth(self.context)
        
        # 4. Activate Auto-Cookie Accepter
        await self._inject_auto_consent(self.context)

        # Return the main page
        return await self.context.new_page()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        # 5. Perform Aggressive Cleanup before closing
        if self.context:
            await self._clean_unnecessary_data(self.context)
            await self.context.close()
            
        if self.browser: await self.browser.close()
        if self.playwright: await self.playwright.stop()

    # --- INTERNAL UTILITIES ---

    async def _activate_ad_blocker(self, context: BrowserContext):
        """Blocks network requests for ads, trackers, and heavy resources."""
        async def route_handler(route):
            req = route.request
            url = req.url.lower()
            resource = req.resource_type

            # Block by Resource Type (Speed)
            if resource in BLOCKED_RESOURCES:
                await route.abort()
                return

            # Block by URL Keywords (Ads/Trackers)
            if any(key in url for key in AD_KEYWORDS):
                await route.abort()
                return

            await route.continue_()

        # Apply routing to all pages in this context
        await context.route("**/*", route_handler)

    async def _activate_smart_popup_killer(self, context: BrowserContext):
        """
        Monitors new tabs. 
        - Closes them if they look like Ads/Spam.
        - Keeps them if they are Trusted File Hosts (Redirects).
        """
        async def on_new_page(page: Page):
            try:
                # Wait briefly for URL/Title to initialize
                try:
                    await page.wait_for_load_state("domcontentloaded", timeout=3000)
                except: pass 

                if page.is_closed(): return
                
                url = page.url.lower()
                
                # ALLOW: Trusted Hosts (Good Redirects)
                if any(host in url for host in TRUSTED_FILE_HOSTS):
                    # print(f"✅ Allowed Download Redirect: {url[:50]}...")
                    return 

                # BLOCK: Ads, Blank pages, or Suspicious Keywords
                if any(k in url for k in AD_KEYWORDS) or url == "about:blank":
                    # print(f"🛡️ Blocked Popup: {url[:50]}...")
                    await page.close()
                else:
                    # Optional: Close unknown popups too if you want strict mode
                    # await page.close()
                    pass
            except Exception:
                # If we can't inspect the page (crashed/lagged), close it safety
                if not page.is_closed(): await page.close()

        context.on("page", on_new_page)

    async def _apply_advanced_stealth(self, context: BrowserContext):
        """Injects JS to mask the bot as a real human browser."""
        stealth_scripts = [
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})",
            "window.chrome = { runtime: {} };",
            "Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });",
            "Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });",
            # Mock Permissions API
            """
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
            );
            """
        ]
        for script in stealth_scripts:
            await context.add_init_script(script)

    async def _inject_auto_consent(self, context: BrowserContext):
        """
        Injects a universal script to automatically click 'Accept'/'Agree' buttons
        for cookies and GDPR popups.
        """
        js_auto_clicker = """
            setInterval(() => {
                const selectors = [
                    'button:has-text("Reject all")', 
                    'button:has-text("Accept all")',
                    '[aria-label="Accept all"]',
                    '#onetrust-accept-btn-handler',
                    '.fc-cta-consent', 
                    '.cc-btn.cc-accept',
                    'button[class*="agree"]',
                    'button[class*="accept"]',
                    'button[class*="consent"]'
                ];

                selectors.forEach(sel => {
                    const els = document.querySelectorAll(sel);
                    els.forEach(el => {
                        if (el.offsetParent !== null && !el.disabled) {
                            el.click();
                        }
                    });
                });
                
                // Text-based fallback
                const buttons = Array.from(document.querySelectorAll('button, a'));
                buttons.forEach(b => {
                    const t = b.innerText.toLowerCase();
                    if ((t.includes('accept') || t.includes('agree') || t.includes('i understand')) && t.length < 20) {
                        b.click();
                    }
                });
            }, 1000);
        """
        await context.add_init_script(js_auto_clicker)

    async def _clean_unnecessary_data(self, context: BrowserContext):
        """
        Uses Chrome DevTools Protocol (CDP) to wipe cache and service workers
        before closing, keeping the server clean.
        """
        try:
            # Get a page to access the CDP session
            page = context.pages[0] if context.pages else await context.new_page()
            client = await context.new_cdp_session(page)
            
            # 1. Clear Browser Cache (Images, Scripts, CSS)
            await client.send("Network.clearBrowserCache")
            
            # 2. Unregister Service Workers (Often used by ads/trackers)
            await client.send("ServiceWorker.stopAllWorkers")
            
            # Note: We do NOT clear cookies here to allow session persistence if needed later
            # await client.send("Network.clearBrowserCookies")
            
        except Exception:
            pass # Ignore errors during cleanup

# Helper function for easy import
def get_safe_browser():
    return SafeBrowser()