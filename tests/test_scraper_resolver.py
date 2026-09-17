import asyncio

from playwright.async_api import Error as PlaywrightError

from core.scraper.platforms import PlatformSpec
from core.scraper.resolver import _check_platform

PLATFORM: PlatformSpec = {
    "name": "github",
    "url": "https://github.com/{username}",
    "bio_selector": None,
}


class _FailingPage:
    def __init__(self):
        self.closed = False

    async def goto(self, url, **kwargs):
        raise PlaywrightError("navigation failed")

    async def close(self):
        self.closed = True


class _StubBrowser:
    def __init__(self, page):
        self._page = page

    async def new_page(self):
        return self._page


def test_navigation_failure_returns_none_and_closes_the_page():
    page = _FailingPage()

    result = asyncio.run(
        _check_platform(
            _StubBrowser(page),
            PLATFORM,
            "seed_user",
            asyncio.Semaphore(1),
        )
    )

    assert result is None
    assert page.closed
