import asyncio
import itertools
from typing import Any

from playwright.async_api import Error as PlaywrightError
import pytest

from core.models import Target
from core.scraper import resolver
from core.scraper.platforms import PlatformSpec
from core.scraper.resolver import _check_platform
from core.scraper.throttle import HostPacer

PLATFORM: PlatformSpec = {
    "name": "github",
    "url": "https://github.com/{username}",
    "bio_selector": ".bio",
}

BIO = "blog https://example.com/me and @secondhandle"


class _Response:
    def __init__(self, status: int):
        self.status = status


class _FailingPage:
    def __init__(self):
        self.closed = False

    async def goto(self, url, **kwargs):
        raise PlaywrightError("navigation failed")

    async def close(self):
        self.closed = True

    def is_closed(self):
        return self.closed


class _BioElement:
    def __init__(self, text: str):
        self._text = text

    async def inner_text(self):
        return self._text


class _BioPage:
    def __init__(self, bio: str = BIO, status: int = 200):
        self.closed = False
        self._bio = bio
        self._status = status

    async def goto(self, url, **kwargs):
        return _Response(self._status)

    async def query_selector(self, selector):
        return _BioElement(self._bio)

    async def close(self):
        self.closed = True

    def is_closed(self):
        return self.closed


class _StubBrowser:
    def __init__(self, page=None):
        self._page = page

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    async def new_page(self):
        return self._page


def _pacer() -> HostPacer:
    return HostPacer(delay=0.0, concurrency=1, budget=50, retries=0)


def _candidate(links: resolver.BioLinks | None = None) -> resolver.PlatformCandidate:
    return {
        "platform": "github",
        "url": "https://github.com/seed_user",
        "username": "seed_user",
        "confidence": 1.0,
        "bio_selector": ".bio",
        "links": links or {"urls": [], "handles": []},
    }


async def _stub_options() -> dict[str, Any]:
    return {}


def _check(page) -> resolver.PlatformCandidate | None:
    return asyncio.run(
        _check_platform(
            _StubBrowser(page),
            PLATFORM,
            "seed_user",
            asyncio.Semaphore(1),
            _pacer(),
        )
    )


def test_navigation_failure_returns_none_and_closes_the_page():
    page = _FailingPage()

    assert _check(page) is None
    assert page.closed


def test_missing_page_returns_none_and_closes_the_page():
    page = _BioPage(status=404)

    assert _check(page) is None
    assert page.closed


def test_confirmed_profile_carries_its_bio_links_and_closes_the_page():
    page = _BioPage()

    result = _check(page)

    assert result is not None
    assert result["links"]["urls"] == ["https://example.com/me"]
    assert result["links"]["handles"] == ["secondhandle"]
    assert page.closed


def test_bio_extraction_leaves_the_page_to_its_owner():
    page = _BioPage()

    links = asyncio.run(resolver.extract_bio_links(page, _candidate()))

    assert links["handles"] == ["secondhandle"]
    assert not page.closed


@pytest.mark.django_db(transaction=True)
def test_discovery_follows_handles_only_and_stops_at_the_cap(monkeypatch):
    target = Target.objects.create(seed_username="seed_user")
    probed: list[str] = []
    counter = itertools.count()

    async def _resolve_username(browser, username, pacer):
        probed.append(username)
        index = next(counter)
        return [
            _candidate(
                {
                    "urls": [f"https://example.com/{index}"],
                    "handles": [f"handle{index}"],
                }
            )
        ]

    monkeypatch.setattr(resolver, "StealthBrowser", _StubBrowser)
    monkeypatch.setattr(resolver, "browser_options", _stub_options)
    monkeypatch.setattr(resolver, "resolve_username", _resolve_username)
    monkeypatch.setattr(resolver, "MAX_DISCOVERY_CANDIDATES", 3)

    asyncio.run(resolver.build_discovery_tree(target.pk, _pacer()))

    assert probed == ["seed_user", "handle0", "handle1"]
