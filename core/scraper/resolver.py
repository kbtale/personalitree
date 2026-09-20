import asyncio
from collections.abc import Iterable
from dataclasses import dataclass
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
from core.scraper.identity import (
    KnownProfiles,
    canonical_url,
    confidence_for,
    profile_exists,
    signals_for,
)
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
    """A profile the platform proved exists, with its links and evidence."""

    platform: str
    url: str
    username: str
    display_name: str
    confidence: float
    signals: list[str]
    bio_selector: str | None
    links: BioLinks


@dataclass
class ProbeContext:
    """Everything one probe shares with the rest of the run."""

    browser: StealthBrowser
    pacer: HostPacer
    known: KnownProfiles
    from_bio: bool


async def _read_display_name(page: Page) -> str:
    """Read the profile's own name, preferring og:title over the document title."""
    meta = await page.query_selector("meta[property='og:title']")
    if meta:
        content = await meta.get_attribute("content")
        if content and content.strip():
            return content.strip()
    title = await page.title()
    return title.strip()


async def _check_platform(
    context: ProbeContext,
    platform: PlatformSpec,
    username: str,
    semaphore: asyncio.Semaphore,
) -> PlatformCandidate | None:
    """Check one platform, prove the profile exists, and always close the page."""
    url = platform["url"].format(username=username)
    async with semaphore:
        page = await context.browser.new_page()
        try:
            response = await fetch(page, url, context.pacer)
            if response is None or response.status != HTTP_OK:
                return None

            content = await page.content()
            if not profile_exists(url, page.url, content, platform):
                logger.debug("%s did not prove a profile exists", url)
                return None

            candidate: PlatformCandidate = {
                "platform": platform["name"],
                "url": url,
                "username": username,
                "display_name": await _read_display_name(page),
                "confidence": 0.0,
                "signals": [],
                "bio_selector": platform.get("bio_selector"),
                "links": {"urls": [], "handles": []},
            }
            candidate["links"] = await extract_bio_links(page, candidate)
            candidate["signals"] = signals_for(
                {
                    "username": username,
                    "display_name": candidate["display_name"],
                    "bio_urls": candidate["links"]["urls"],
                    "from_bio": context.from_bio,
                },
                context.known,
            )
            candidate["confidence"] = confidence_for(candidate["signals"])
            return candidate
        except PlaywrightError as exc:
            logger.debug("Failed to check %s: %s", url, exc)
            return None
        finally:
            await StealthBrowser.close_page(page)


async def resolve_username(
    context: ProbeContext,
    username: str,
) -> list[PlatformCandidate]:
    """Resolve a username across all configured platforms."""
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    tasks = [
        _check_platform(context, platform, username, semaphore)
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
    queue: list[tuple[str, int, bool]],
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
        queue.append((candidate, depth + 1, True))
    return False


def _known_profiles(target: Target) -> KnownProfiles:
    """Collect what the target's confirmed rows already prove."""
    accounts = list(target.discovered_accounts.all())
    return {
        "handles": {account.username.lower() for account in accounts},
        "names": {
            account.display_name.lower() for account in accounts if account.display_name
        },
        "urls": {canonical_url(account.url) for account in accounts},
    }


def _remember(known: KnownProfiles, result: PlatformCandidate) -> None:
    """Add a freshly confirmed profile to what is known, for later probes."""
    known["handles"].add(result["username"].lower())
    if result["display_name"]:
        known["names"].add(result["display_name"].lower())
    known["urls"].add(canonical_url(result["url"]))


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
    known = await asyncio.to_thread(_known_profiles, target)
    seen_usernames: set[str] = {seed.lower()}
    queue: list[tuple[str, int, bool]] = [(seed, 0, False)]
    capped = False

    options = await browser_options()
    async with StealthBrowser(**options) as browser:
        while queue and not capped:
            username, depth, from_bio = queue.pop(0)

            if depth > max_depth:
                continue

            logger.info("Resolving '%s' (depth %d/%d)", username, depth, max_depth)

            context = ProbeContext(
                browser=browser,
                pacer=pacer,
                known=known,
                from_bio=from_bio,
            )
            confirmed = await resolve_username(context, username)

            for result in confirmed:
                await asyncio.to_thread(
                    _save_discovered_account,
                    target,
                    result,
                )
                _remember(known, result)

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
            "display_name": result["display_name"],
            "confidence": result["confidence"],
            "signals": result["signals"],
        },
    )
