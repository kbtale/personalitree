import logging

from playwright.async_api import Page

from core.scraper.browser import StealthBrowser

logger = logging.getLogger(__name__)

DEFAULT_SCROLL_STEPS = 6


async def scrape_profile_content(
    browser: StealthBrowser,
    page: Page,
    platform_name: str,
) -> dict:
    """
    Extract visible text content and metadata from an already-loaded profile page.
    Returns a dict with 'raw_text' and 'metadata'.
    """
    raw_text = ""
    metadata: dict = {}

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

    except Exception as exc:
        logger.warning(
            "Content extraction failed for '%s': %s", platform_name, exc
        )

    return {"raw_text": raw_text.strip(), "metadata": metadata}
