import asyncio
import logging
import re
from typing import TypedDict

from lxml import html as lxml_html
from lxml.etree import ParserError
from playwright.async_api import Error as PlaywrightError, Page

from core.constants import HTTP_OK
from core.models import DiscoveredAccount, Target
from core.scraper.browser import StealthBrowser
from core.scraper.platforms import PLATFORMS, PlatformSpec

logger = logging.getLogger(__name__)

CONCURRENCY_LIMIT = 5

URL_PATTERN = re.compile(r"https?://[^\s\"'<>)\]},]+", re.IGNORECASE)

HANDLE_PATTERN = re.compile(r"(?<!\w)@([A-Za-z0-9_.]{2,30})(?!\w)")


class PlatformCandidate(TypedDict):
    """A username confirmed to exist on a platform, with its live page."""

    platform: str
    url: str
    username: str
    confidence: float
    bio_selector: str | None
    page: Page


async def _check_platform(
    browser: StealthBrowser,
    platform: PlatformSpec,
    username: str,
    semaphore: asyncio.Semaphore,
) -> PlatformCandidate | None:
    """Check if a username exists on a single platform."""
    url = platform["url"].format(username=username)
    async with semaphore:
        page = await browser.new_page()
        response = None
        try:
            response = await page.goto(
                url, wait_until="domcontentloaded", timeout=15000
            )
            if response and response.status == HTTP_OK:
                return {
                    "platform": platform["name"],
                    "url": url,
                    "username": username,
                    "confidence": 1.0,
                    "bio_selector": platform.get("bio_selector"),
                    "page": page,
                }
            return None
        except PlaywrightError as exc:
            logger.debug("Failed to check %s: %s", url, exc)
            return None
        finally:
            if not (response and response.status == HTTP_OK):
                await page.close()


async def resolve_username(
    browser: StealthBrowser,
    username: str,
) -> list[PlatformCandidate]:
    """Resolve a username across all configured platforms."""
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    tasks = [
        _check_platform(browser, platform, username, semaphore)
        for platform in PLATFORMS
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    confirmed: list[PlatformCandidate] = []
    for result in results:
        if isinstance(result, Exception):
            logger.warning("Platform check raised: %s", result)
        elif result is not None:
            confirmed.append(result)

    logger.info(
        "Resolved '%s': %d/%d platforms confirmed",
        username,
        len(confirmed),
        len(PLATFORMS),
    )
    return confirmed


async def extract_bio_links(
    page: Page, platform_result: PlatformCandidate
) -> list[str]:
    """Extract URLs and handles from a confirmed profile's bio."""
    discovered = []
    bio_text = ""

    bio_selector = platform_result.get("bio_selector")

    try:
        if bio_selector:
            element = await page.query_selector(bio_selector)
            if element:
                bio_text = await element.inner_text()
        else:
            meta = await page.query_selector("meta[property='og:description']")
            if meta:
                bio_text = await meta.get_attribute("content") or ""

            if not bio_text:
                meta = await page.query_selector("meta[name='description']")
                if meta:
                    bio_text = await meta.get_attribute("content") or ""

        if not bio_text:
            content = await page.content()
            tree = lxml_html.fromstring(content)
            desc_nodes = tree.xpath("//meta[@name='description']/@content")
            if desc_nodes:
                bio_text = desc_nodes[0]

        urls = URL_PATTERN.findall(bio_text)
        handles = HANDLE_PATTERN.findall(bio_text)

        discovered.extend(urls)
        discovered.extend(handles)

    except (PlaywrightError, ParserError) as exc:
        logger.warning(
            "Bio extraction failed for %s: %s",
            platform_result["platform"],
            exc,
        )
    finally:
        await page.close()

    return discovered


async def build_discovery_tree(target_id: int, max_depth: int = 2) -> None:
    """
    Main entry point for identity discovery.
    Resolves usernames across platforms, extracts bio links,
    and resolves inferred handles.
    """
    target = await asyncio.to_thread(Target.objects.fetch, target_id)
    seed = target.seed_username
    seen_usernames: set[str] = {seed.lower()}
    queue: list[tuple[str, int]] = [(seed, 0)]

    async with StealthBrowser() as browser:
        while queue:
            username, depth = queue.pop(0)

            if depth > max_depth:
                continue

            logger.info("Resolving '%s' (depth %d/%d)", username, depth, max_depth)

            confirmed = await resolve_username(browser, username)

            for result in confirmed:
                await asyncio.to_thread(
                    _save_discovered_account,
                    target,
                    result,
                )

                page = result.get("page")
                if page:
                    new_links = await extract_bio_links(page, result)

                    for link in new_links:
                        handle = link.lower().strip("@").strip("/")
                        if handle and handle not in seen_usernames:
                            seen_usernames.add(handle)
                            queue.append((handle, depth + 1))

    logger.info(
        "Discovery tree complete for '%s': %d unique handles explored",
        seed,
        len(seen_usernames),
    )


def _save_discovered_account(target: Target, result: PlatformCandidate) -> None:
    """Save or update a DiscoveredAccount row (sync, called via to_thread)."""
    DiscoveredAccount.objects.update_or_create(
        target=target,
        platform_name=result["platform"],
        username=result["username"],
        defaults={
            "url": result["url"],
            "verification_confidence": result["confidence"],
        },
    )
