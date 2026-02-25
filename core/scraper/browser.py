import asyncio
import logging
import random
from contextlib import asynccontextmanager

from playwright.async_api import Browser, Page, async_playwright
from playwright_stealth import stealth_async

logger = logging.getLogger(__name__)

DEFAULT_VIEWPORT = {"width": 1920, "height": 1080}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
]


class StealthBrowser:
    """Async context manager for a stealth-patched Playwright Chromium browser."""

    def __init__(self, proxy_url: str | None = None):
        self._proxy_url = proxy_url
        self._playwright = None
        self._browser: Browser | None = None

    async def __aenter__(self) -> "StealthBrowser":
        self._playwright = await async_playwright().start()

        launch_args: dict = {
            "headless": True,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        }

        if self._proxy_url:
            launch_args["proxy"] = {"server": self._proxy_url}

        self._browser = await self._playwright.chromium.launch(**launch_args)
        logger.info("StealthBrowser launched (proxy=%s)", self._proxy_url or "none")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        logger.info("StealthBrowser closed")

    async def new_page(self) -> Page:
        """Create a new browser page with a random user-agent and stealth patches."""
        context = await self._browser.new_context(
            viewport=DEFAULT_VIEWPORT,
            user_agent=random.choice(USER_AGENTS),
        )
        page = await context.new_page()
        await stealth_async(page)
        return page

    @staticmethod
    async def random_delay(min_s: float = 1.0, max_s: float = 3.5) -> None:
        """Random pause to simulate human reaction time between actions."""
        await asyncio.sleep(random.uniform(min_s, max_s))

    @staticmethod
    async def human_scroll(page: Page, steps: int = 5) -> None:
        """Scroll down a page in randomized steps to simulate reading."""
        for _ in range(steps):
            distance = random.randint(200, 600)
            await page.mouse.wheel(0, distance)
            await asyncio.sleep(random.uniform(0.3, 1.2))


def _get_proxy_url() -> str | None:
    """Read proxy configuration from the Settings model."""
    try:
        from core.models import Settings

        setting = Settings.objects.filter(key="PROXY_URL").first()
        if setting and setting.value:
            return setting.value
    except Exception:
        pass
    return None


@asynccontextmanager
async def create_browser():
    """Convenience factory that reads proxy config from the database."""
    proxy = _get_proxy_url()
    async with StealthBrowser(proxy_url=proxy) as browser:
        yield browser
