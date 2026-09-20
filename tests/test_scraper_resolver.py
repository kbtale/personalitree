import asyncio
import itertools

from playwright.async_api import Error as PlaywrightError
import pytest

from core.models import Target
from core.scraper import resolver
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
    def __init__(self, page=None):
        self._page = page

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None

    async def new_page(self):
        return self._page


class _BioElement:
    def __init__(self, text: str):
        self._text = text

    async def inner_text(self):
        return self._text


class _BioPage:
    def __init__(self, bio: str):
        self.closed = False
        self._bio = bio

    async def query_selector(self, selector):
        return _BioElement(self._bio)

    async def close(self):
        self.closed = True


def _candidate(page) -> resolver.PlatformCandidate:
    return {
        "platform": "github",
        "url": "https://github.com/seed_user",
        "username": "seed_user",
        "confidence": 1.0,
        "bio_selector": ".bio",
        "page": page,
    }


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


def test_bio_links_separate_urls_from_handles():
    page = _BioPage("blog https://example.com/me and @secondhandle")

    links = asyncio.run(resolver.extract_bio_links(page, _candidate(page)))

    assert links["urls"] == ["https://example.com/me"]
    assert links["handles"] == ["secondhandle"]
    assert page.closed


@pytest.mark.django_db(transaction=True)
def test_discovery_follows_handles_only_and_stops_at_the_cap(monkeypatch):
    target = Target.objects.create(seed_username="seed_user")
    probed: list[str] = []
    counter = itertools.count()

    async def _resolve_username(browser, username):
        probed.append(username)
        return [_candidate(object())]

    async def _extract_bio_links(page, platform_result):
        index = next(counter)
        return {
            "urls": [f"https://example.com/{index}"],
            "handles": [f"handle{index}"],
        }

    monkeypatch.setattr(resolver, "StealthBrowser", _StubBrowser)
    monkeypatch.setattr(resolver, "resolve_username", _resolve_username)
    monkeypatch.setattr(resolver, "extract_bio_links", _extract_bio_links)
    monkeypatch.setattr(resolver, "MAX_DISCOVERY_CANDIDATES", 3)

    asyncio.run(resolver.build_discovery_tree(target.pk))

    assert probed == ["seed_user", "handle0", "handle1"]
