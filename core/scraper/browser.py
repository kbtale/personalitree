import logging
from contextlib import asynccontextmanager

from playwright.async_api import Browser, Page, async_playwright
from playwright_stealth import stealth_async

logger = logging.getLogger(__name__)

DEFAULT_VIEWPORT = {"width": 1920, "height": 1080}

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)


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
        """Create a new browser page with stealth patches applied."""
        context = await self._browser.new_context(
            viewport=DEFAULT_VIEWPORT,
            user_agent=DEFAULT_USER_AGENT,
        )
        page = await context.new_page()
        await stealth_async(page)
        return page


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
