import asyncio
from collections.abc import Iterable
import logging
import re
from typing import TypedDict

from lxml import html as lxml_html
from lxml.etree import ParserError
from playwright.async_api import Error as PlaywrightError, Page

from core.constants import (
    HTTP_OK,
    MAX_DISCOVERY_CANDIDATES,
    MAX_DISCOVERY_DEPTH,
)
from core.models import DiscoveredAccount, Target
from core.scraper.browser import StealthBrowser, browser_options
from core.scraper.platforms import PLATFORMS, PlatformSpec
from core.scraper.throttle import HostPacer, fetch

logger = logging.getLogger(__name__)

CONCURRENCY_LIMIT = 5

URL_PATTERN = re.compile(r"https?://[^\s\"'<>)\]},]+", re.IGNORECASE)

HANDLE_PATTERN = re.compile(r"(?<!\w)@([A-Za-z0-9_.]{2,30})(?!\w)")


class BioLinks(TypedDict):
    """The URLs and handles a profile bio points at."""

    urls: list[str]
    handles: list[str]


class PlatformCandidate(TypedDict):
    """A confirmed profile and the handles its bio points at."""

    platform: str
    url: str
    username: str
    confidence: float
    bio_selector: str | None
    links: BioLinks


async def _check_platform(
    browser: StealthBrowser,
    platform: PlatformSpec,
    username: str,
    semaphore: asyncio.Semaphore,
    pacer: HostPacer,
) -> PlatformCandidate | None:
    """Check one platform, read the bio, and always close the page before returning."""
    url = platform["url"].format(username=username)
    async with semaphore:
        page = await browser.new_page()
        try:
            response = await fetch(page, url, pacer)
            if response is None or response.status != HTTP_OK:
                return None

            candidate: PlatformCandidate = {
                "platform": platform["name"],
                "url": url,
                "username": username,
                "confidence": 1.0,
                "bio_selector": platform.get("bio_selector"),
                "links": {"urls": [], "handles": []},
            }
            candidate["links"] = await extract_bio_links(page, candidate)
            return candidate
        except PlaywrightError as exc:
            logger.debug("Failed to check %s: %s", url, exc)
            return None
        finally:
            await StealthBrowser.close_page(page)


async def resolve_username(
    browser: StealthBrowser,
    username: str,
    pacer: HostPacer,
) -> list[PlatformCandidate]:
    """Resolve a username across all configured platforms."""
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    tasks = [
        _check_platform(browser, platform, username, semaphore, pacer)
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


async def extract_bio_links(page: Page, platform_result: PlatformCandidate) -> BioLinks:
    """Extract the URLs and handles a bio points at; the caller owns the page."""
    urls: list[str] = []
    handles: list[str] = []
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

    except (PlaywrightError, ParserError) as exc:
        logger.warning(
            "Bio extraction failed for %s: %s",
            platform_result["platform"],
            exc,
        )

    return {"urls": urls, "handles": handles}


def _extend_queue(
    queue: list[tuple[str, int]],
    seen_usernames: set[str],
    handles: Iterable[str],
    depth: int,
) -> bool:
    """Queue unseen handles and report whether the candidate cap was reached."""
    for handle in handles:
        candidate = handle.lower().strip("@").strip("/")
        if not candidate or candidate in seen_usernames:
            continue
        if len(seen_usernames) >= MAX_DISCOVERY_CANDIDATES:
            return True
        seen_usernames.add(candidate)
        queue.append((candidate, depth + 1))
    return False


async def build_discovery_tree(
    target_id: int,
    pacer: HostPacer,
    max_depth: int = MAX_DISCOVERY_DEPTH,
) -> None:
    """
    Main entry point for identity discovery.
    Resolves usernames across platforms, reads the handles their bios point at,
    and resolves those handles one level deeper.
    """
    target = await asyncio.to_thread(Target.objects.fetch, target_id)
    seed = target.seed_username
    seen_usernames: set[str] = {seed.lower()}
    queue: list[tuple[str, int]] = [(seed, 0)]
    capped = False

    options = await browser_options()
    async with StealthBrowser(**options) as browser:
        while queue and not capped:
            username, depth = queue.pop(0)

            if depth > max_depth:
                continue

            logger.info("Resolving '%s' (depth %d/%d)", username, depth, max_depth)

            confirmed = await resolve_username(browser, username, pacer)

            for result in confirmed:
                await asyncio.to_thread(
                    _save_discovered_account,
                    target,
                    result,
                )

                if _extend_queue(
                    queue,
                    seen_usernames,
                    result["links"]["handles"],
                    depth,
                ):
                    logger.warning(
                        "Discovery cap of %d candidates reached for '%s'",
                        MAX_DISCOVERY_CANDIDATES,
                        seed,
                    )
                    capped = True

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
