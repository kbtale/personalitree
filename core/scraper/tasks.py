import asyncio
import logging
from typing import Any

from django.db.models import F
from playwright.async_api import Error as PlaywrightError

from core.constants import MAX_SCRAPE_ACCOUNTS, MAX_SCRAPE_ATTEMPTS, PAGE_TIMEOUT_MS
from core.exceptions import PersonaliTreeError
from core.llm.pipeline import run_evaluation_pipeline
from core.models import DiscoveredAccount, RawScrape, Target
from core.scraper.auth import attempt_login, detect_login_wall
from core.scraper.browser import StealthBrowser, create_browser
from core.scraper.extractor import scrape_profile_content
from core.scraper.queue import enqueue_scrape
from core.scraper.resolver import build_discovery_tree

logger = logging.getLogger(__name__)


def scrape_target(target_id: int) -> None:
    """
    Django Q2 task entry point.
    Accepts a target_id, runs the full scraping pipeline, and saves results.
    """
    _start_attempt(target_id)
    try:
        asyncio.run(_run_pipeline(target_id))
    except PersonaliTreeError as exc:
        logger.exception("Scrape attempt failed for target %d", target_id)
        _handle_failure(target_id, str(exc))


def _start_attempt(target_id: int) -> None:
    """Count the attempt and move the target into the scraping state."""
    Target.objects.filter(id=target_id).update(
        attempts=F("attempts") + 1,
        status=Target.Status.SCRAPING,
    )


def _handle_failure(target_id: int, error: str) -> None:
    """Re-queue the target while attempts remain, otherwise record the failure."""
    target = Target.objects.filter(id=target_id).first()
    if target is None:
        return

    if target.attempts >= MAX_SCRAPE_ATTEMPTS:
        Target.objects.filter(id=target_id).update(
            status=Target.Status.FAILED,
            last_error=error,
        )
        logger.error(
            "Target %d failed after %d attempt(s): %s",
            target_id,
            target.attempts,
            error,
        )
        return

    logger.warning(
        "Re-queueing target %d after attempt %d of %d",
        target_id,
        target.attempts,
        MAX_SCRAPE_ATTEMPTS,
    )
    target.status = Target.Status.PENDING
    target.save(update_fields=["status"])
    enqueue_scrape(target)


async def _run_pipeline(target_id: int) -> None:
    logger.info("Pipeline started for target_id=%d", target_id)

    await build_discovery_tree(target_id)

    target = await asyncio.to_thread(Target.objects.fetch, target_id)
    accounts = await asyncio.to_thread(
        list,
        target.discovered_accounts.all()[:MAX_SCRAPE_ACCOUNTS],
    )
    logger.info("Scraping %d accounts for target %d", len(accounts), target_id)

    async with create_browser() as browser:
        for account in accounts:
            await _scrape_account(browser, target_id, account)

    await run_evaluation_pipeline(target_id)
    logger.info("Pipeline complete for target_id=%d", target_id)


async def _scrape_account(
    browser: StealthBrowser,
    target_id: int,
    account: DiscoveredAccount,
) -> None:
    page = await browser.new_page()
    try:
        await page.goto(
            account.url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS
        )
        await browser.random_delay()

        if await detect_login_wall(page):
            logger.info("Login wall detected on '%s'", account.platform_name)
            await page.close()
            page = await attempt_login(browser, account.platform_name)
            if not page:
                logger.warning(
                    "Skipping '%s', no valid credentials",
                    account.platform_name,
                )
                return
            await page.goto(
                account.url, wait_until="domcontentloaded", timeout=PAGE_TIMEOUT_MS
            )
            await browser.random_delay()

        content = await scrape_profile_content(browser, page, account.platform_name)

        if content["raw_text"]:
            await asyncio.to_thread(
                _save_raw_scrape,
                target_id,
                account.platform_name,
                content["raw_text"],
                content["metadata"],
            )

    except PlaywrightError as exc:
        logger.exception("Failed to scrape '%s': %s", account.url, exc)
    finally:
        if page and not page.is_closed():
            await page.close()


def _save_raw_scrape(
    target_id: int,
    platform_name: str,
    raw_text: str,
    metadata: dict[str, Any],
) -> None:
    target = Target.objects.fetch(target_id)
    RawScrape.objects.update_or_create(
        target=target,
        platform_name=platform_name,
        defaults={
            "raw_text_dump": raw_text,
            "metadata_json": metadata,
        },
    )
