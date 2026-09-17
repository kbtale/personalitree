import logging
from typing import Any, TypedDict

from playwright.async_api import Error as PlaywrightError, Page

from core.scraper.browser import StealthBrowser

logger = logging.getLogger(__name__)

DEFAULT_SCROLL_STEPS = 6


class ScrapeContent(TypedDict):
    """Text and metadata extracted from a loaded profile page."""

    raw_text: str
    metadata: dict[str, Any]


async def scrape_profile_content(
    browser: StealthBrowser,
    page: Page,
    platform_name: str,
) -> ScrapeContent:
    """
    Extract visible text content and metadata from an already-loaded profile page.
    Returns a dict with 'raw_text' and 'metadata'.
    """
    raw_text = ""
    metadata: dict[str, Any] = {}

    try:
        await browser.human_scroll(page, steps=DEFAULT_SCROLL_STEPS)
        await browser.random_delay(0.5, 1.5)

        raw_text = await page.inner_text("body")

        title = await page.title()
        url = page.url

        metadata = {
            "title": title,
            "url": url,
            "platform": platform_name,
        }

    except PlaywrightError as exc:
        logger.warning("Content extraction failed for '%s': %s", platform_name, exc)

    return {"raw_text": raw_text.strip(), "metadata": metadata}
