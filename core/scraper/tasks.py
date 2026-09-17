import asyncio
import logging
from typing import Any

from playwright.async_api import Error as PlaywrightError

from core.llm.pipeline import run_evaluation_pipeline
from core.models import DiscoveredAccount, RawScrape, Target
from core.scraper.auth import attempt_login, detect_login_wall
from core.scraper.browser import StealthBrowser, create_browser
from core.scraper.extractor import scrape_profile_content
from core.scraper.resolver import build_discovery_tree

logger = logging.getLogger(__name__)


def scrape_target(target_id: int) -> None:
    """
    Django Q2 task entry point.
    Accepts a target_id, runs the full scraping pipeline, and saves results.
    """
    asyncio.run(_run_pipeline(target_id))


async def _run_pipeline(target_id: int) -> None:
    await asyncio.to_thread(
        Target.objects.filter(id=target_id).update,
        status=Target.Status.SCRAPING,
    )
    logger.info("Pipeline started for target_id=%d", target_id)

    await build_discovery_tree(target_id)

    target = await asyncio.to_thread(Target.objects.fetch, target_id)
    accounts = await asyncio.to_thread(list, target.discovered_accounts.all())

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
        await page.goto(account.url, wait_until="domcontentloaded", timeout=15000)
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
            await page.goto(account.url, wait_until="domcontentloaded", timeout=15000)
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
