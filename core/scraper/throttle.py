"""
Per-host pacing and rate-limit backoff for scraper requests.
"""

import asyncio
from collections import defaultdict
import logging
import time
from urllib.parse import urlsplit

from playwright.async_api import Page, Response

from core.constants import (
    DEFAULT_RATE_LIMIT_BACKOFF_SECONDS,
    DEFAULT_SCRAPE_HOST_CONCURRENCY,
    DEFAULT_SCRAPE_HOST_DELAY_SECONDS,
    DEFAULT_SCRAPE_HOST_REQUEST_BUDGET,
    DEFAULT_SCRAPE_MAX_RETRIES,
    HTTP_SERVICE_UNAVAILABLE,
    HTTP_TOO_MANY_REQUESTS,
    MAX_RATE_LIMIT_BACKOFF_SECONDS,
    PAGE_TIMEOUT_MS,
    ConfigKey,
)
from core.utils.config import get_config

logger = logging.getLogger(__name__)

RATE_LIMITED_STATUSES = (HTTP_TOO_MANY_REQUESTS, HTTP_SERVICE_UNAVAILABLE)


class HostPacer:
    """Keeps one request in flight per host, spaces requests out and bounds a run."""

    def __init__(
        self,
        delay: float,
        concurrency: int,
        budget: int,
        retries: int,
    ) -> None:
        self._delay = delay
        self._concurrency = concurrency
        self._budget = budget
        self._retries = retries
        self._slots: dict[str, asyncio.Semaphore] = {}
        self._next_allowed: dict[str, float] = defaultdict(float)
        self._used: dict[str, int] = defaultdict(int)
        self._reported: set[str] = set()

    @property
    def retries(self) -> int:
        """How many times a rate-limited request is retried."""
        return self._retries

    @classmethod
    def from_config(cls) -> "HostPacer":
        """Build a pacer from configuration; call it off the event loop."""
        return cls(
            delay=float(
                get_config(
                    ConfigKey.SCRAPE_HOST_DELAY_SECONDS,
                    str(DEFAULT_SCRAPE_HOST_DELAY_SECONDS),
                )
            ),
            concurrency=int(
                get_config(
                    ConfigKey.SCRAPE_HOST_CONCURRENCY,
                    str(DEFAULT_SCRAPE_HOST_CONCURRENCY),
                )
            ),
            budget=int(
                get_config(
                    ConfigKey.SCRAPE_HOST_REQUEST_BUDGET,
                    str(DEFAULT_SCRAPE_HOST_REQUEST_BUDGET),
                )
            ),
            retries=int(
                get_config(
                    ConfigKey.SCRAPE_MAX_RETRIES,
                    str(DEFAULT_SCRAPE_MAX_RETRIES),
                )
            ),
        )

    @staticmethod
    def host_of(url: str) -> str:
        """Return the host part of a URL, which is what pacing is keyed on."""
        return urlsplit(url).netloc

    def requests_made(self, host: str) -> int:
        """How many requests this run has sent to a host."""
        return self._used[host]

    async def wait(self, host: str) -> bool:
        """Wait for the host's next slot; return False once its budget is spent."""
        async with self._slot(host):
            self._used[host] += 1
            if self._used[host] > self._budget:
                if host not in self._reported:
                    self._reported.add(host)
                    logger.warning(
                        "Budget of %d requests spent for %s, skipping further requests",
                        self._budget,
                        host,
                    )
                return False

            delay = self._next_allowed[host] - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            self._next_allowed[host] = time.monotonic() + self._delay
            return True

    def back_off(self, host: str, seconds: float | None) -> None:
        """Record a rate-limited response so the next request for the host waits."""
        wait_for = DEFAULT_RATE_LIMIT_BACKOFF_SECONDS if seconds is None else seconds
        wait_for = min(max(wait_for, 0.0), MAX_RATE_LIMIT_BACKOFF_SECONDS)
        self._next_allowed[host] = max(
            self._next_allowed[host], time.monotonic() + wait_for
        )
        logger.info(
            "Backing off %s for %.1fs after a rate-limit response", host, wait_for
        )

    def _slot(self, host: str) -> asyncio.Semaphore:
        slot = self._slots.get(host)
        if slot is None:
            slot = asyncio.Semaphore(self._concurrency)
            self._slots[host] = slot
        return slot

    @staticmethod
    def is_rate_limited(response: Response | None) -> bool:
        """Whether a response asks us to slow down."""
        return response is not None and response.status in RATE_LIMITED_STATUSES

    @staticmethod
    def retry_after_seconds(response: Response | None) -> float | None:
        """Read a numeric Retry-After header; the HTTP-date form is ignored."""
        headers = getattr(response, "headers", None) or {}
        raw = headers.get("retry-after")
        if raw is None:
            return None
        try:
            return float(raw)
        except ValueError:
            return None


async def fetch(page: Page, url: str, pacer: HostPacer) -> Response | None:
    """Navigate with pacing, retrying while the host rate-limits us."""
    host = pacer.host_of(url)
    response: Response | None = None

    for attempt in range(pacer.retries + 1):
        if not await pacer.wait(host):
            return None
        response = await page.goto(
            url,
            wait_until="domcontentloaded",
            timeout=PAGE_TIMEOUT_MS,
        )
        if not pacer.is_rate_limited(response):
            return response
        pacer.back_off(host, pacer.retry_after_seconds(response))
        if attempt < pacer.retries:
            logger.info("Rate limited by %s, retrying", host)

    return response
