import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import logging
import random
from types import TracebackType
from typing import Any

from django.core.exceptions import (
    AppRegistryNotReady,
    ImproperlyConfigured,
    SynchronousOnlyOperation,
)
from django.db.utils import OperationalError, ProgrammingError
from playwright.async_api import (
    Browser,
    BrowserContext,
    Error as PlaywrightError,
    Page,
    Playwright,
    async_playwright,
)
from playwright_stealth import stealth_async

from core.constants import CONTEXT_PAGE_LIMIT, ConfigKey
from core.exceptions import BrowserLaunchError

logger = logging.getLogger(__name__)

DEFAULT_VIEWPORT = {"width": 1920, "height": 1080}

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.3 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
]


class StealthBrowser:
    """Async context manager owning one browser and a reused browsing context."""

    def __init__(self, proxy_url: str | None = None) -> None:
        self._proxy_url = proxy_url
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._pages_in_context = 0

    async def __aenter__(self) -> "StealthBrowser":
        launch_args = self._launch_args()
        try:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(**launch_args)
        except PlaywrightError as exc:
            await self._shutdown()
            raise BrowserLaunchError(str(exc)) from exc

        logger.info("StealthBrowser launched (proxy=%s)", self._proxy_url or "none")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self._shutdown()
        logger.info(
            "StealthBrowser closed after %d page(s) in %s context(s)",
            self._pages_in_context,
            "a recycled" if self._context is None else "the current",
        )

    def _launch_args(self) -> dict[str, Any]:
        """Build the Chromium launch options, including the proxy when configured."""
        launch_args: dict[str, Any] = {
            "headless": True,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        }
        if self._proxy_url:
            launch_args["proxy"] = {"server": self._proxy_url}
        return launch_args

    async def _shutdown(self) -> None:
        """Close the context, the browser and the driver, tolerating partial startup."""
        if self._context:
            await self._context.close()
            self._context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    async def new_page(self) -> Page:
        """Open a page in the reused context, with stealth patches applied."""
        context = await self._ensure_context()
        page = await context.new_page()
        await stealth_async(page)
        self._pages_in_context += 1
        return page

    @staticmethod
    async def close_page(page: Page) -> None:
        """Close a page if it is still open, whatever went wrong before."""
        if not page.is_closed():
            await page.close()

    async def _ensure_context(self) -> BrowserContext:
        """Reuse one context, recycling it after CONTEXT_PAGE_LIMIT pages."""
        if self._context is not None and self._pages_in_context >= CONTEXT_PAGE_LIMIT:
            logger.info(
                "Recycling browser context after %d pages", self._pages_in_context
            )
            await self._context.close()
            self._context = None

        if self._context is None:
            self._context = await self._browser.new_context(
                viewport=DEFAULT_VIEWPORT,
                user_agent=random.choice(USER_AGENTS),
            )
            self._pages_in_context = 0
        return self._context

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

        setting = Settings.objects.filter(key=ConfigKey.PROXY_URL).first()
    except (
        AppRegistryNotReady,
        ImproperlyConfigured,
        OperationalError,
        ProgrammingError,
        SynchronousOnlyOperation,
    ):
        return None
    if setting and setting.value:
        return setting.value
    return None


async def browser_options() -> dict[str, Any]:
    """Resolve the browser options from configuration, off the event loop."""
    return {"proxy_url": await asyncio.to_thread(_get_proxy_url)}


@asynccontextmanager
async def create_browser() -> AsyncIterator[StealthBrowser]:
    """Convenience factory that reads proxy config from the database."""
    options = await browser_options()
    async with StealthBrowser(**options) as browser:
        yield browser
