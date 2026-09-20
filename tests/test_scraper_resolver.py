import asyncio
import itertools
from typing import Any

from playwright.async_api import Error as PlaywrightError
import pytest

from core.constants import Signal
from core.models import DiscoveredAccount, Target
from core.scraper import resolver
from core.scraper.identity import KnownProfiles
from core.scraper.platforms import PlatformSpec
from core.scraper.resolver import ProbeContext, _check_platform
from core.scraper.throttle import HostPacer

PLATFORM: PlatformSpec = {
    "name": "github",
    "url": "https://github.com/{username}",
    "bio_selector": ".bio",
}

BIO = "blog https://example.com/me and @secondhandle"
CLEAN_HTML = "<html><body>a profile</body></html>"
NOT_FOUND_HTML = "<html><body>Sorry, this user does not exist</body></html>"
PROFILE_URL = "https://github.com/seed_user"

KNOWN: KnownProfiles = {"handles": {"seed_user"}, "names": set(), "urls": set()}


class _Response:
    def __init__(self, status: int):
        self.status = status


class _Element:
    def __init__(self, text: str):
        self._text = text

    async def inner_text(self):
        return self._text

    async def get_attribute(self, name):
        return self._text


class _Page:
    """Stub page exposing the four calls a probe makes."""

    name = "Seed User"

    def __init__(
        self,
        status: int = 200,
        final_url: str = PROFILE_URL,
        html: str = CLEAN_HTML,
        fail: bool = False,
    ):
        self.closed = False
        self._status = status
        self._final_url = final_url
        self._html = html
        self._fail = fail

    @property
    def url(self):
        return self._final_url

    async def goto(self, url, **kwargs):
        if self._fail:
            raise PlaywrightError("navigation failed")
        return _Response(self._status)

    async def content(self):
        return self._html

    async def title(self):
        return self.name

    async def query_selector(self, selector):
        if "og:title" in selector:
            return _Element(self.name)
        if selector == ".bio":
            return _Element(BIO)
        return None

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
        "url": PROFILE_URL,
        "username": "seed_user",
        "display_name": "Seed User",
        "confidence": 0.4,
        "signals": [Signal.EXISTENCE_PROVEN, Signal.HANDLE_MATCHES_SEED],
        "bio_selector": ".bio",
        "links": links or {"urls": [], "handles": []},
    }


def _context(page, known: KnownProfiles | None = None) -> ProbeContext:
    return ProbeContext(
        browser=_StubBrowser(page),
        pacer=_pacer(),
        known=known or KNOWN,
        from_bio=False,
    )


async def _stub_options() -> dict[str, Any]:
    return {}


def _check(page, known: KnownProfiles | None = None):
    return asyncio.run(
        _check_platform(
            _context(page, known),
            PLATFORM,
            "seed_user",
            asyncio.Semaphore(1),
        )
    )


def test_navigation_failure_returns_none_and_closes_the_page():
    page = _Page(fail=True)

    assert _check(page) is None
    assert page.closed


def test_a_missing_page_returns_none_and_closes_the_page():
    page = _Page(status=404)

    assert _check(page) is None
    assert page.closed


def test_a_redirect_away_from_the_profile_proves_nothing():
    page = _Page(final_url="https://github.com/")

    assert _check(page) is None
    assert page.closed


def test_a_not_found_marker_proves_nothing():
    page = _Page(html=NOT_FOUND_HTML)

    assert _check(page) is None
    assert page.closed


def test_a_proven_profile_carries_its_name_links_and_signals():
    page = _Page()

    result = _check(page)

    assert result is not None
    assert result["display_name"] == "Seed User"
    assert result["links"]["handles"] == ["secondhandle"]
    assert result["signals"] == [Signal.EXISTENCE_PROVEN, Signal.HANDLE_MATCHES_SEED]
    assert result["confidence"] == 0.4
    assert page.closed


def test_bio_extraction_leaves_the_page_to_its_owner():
    page = _Page()

    links = asyncio.run(resolver.extract_bio_links(page, _candidate()))

    assert links["handles"] == ["secondhandle"]
    assert not page.closed


@pytest.mark.django_db(transaction=True)
def test_discovery_follows_handles_only_and_stops_at_the_cap(monkeypatch):
    target = Target.objects.create(seed_username="seed_user")
    probed: list[str] = []
    counter = itertools.count()

    async def _resolve_username(context, username):
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


@pytest.mark.django_db(transaction=True)
def test_a_soft_404_records_nothing(monkeypatch):
    target = Target.objects.create(seed_username="seed_user")
    monkeypatch.setattr(resolver, "browser_options", _stub_options)
    monkeypatch.setattr(resolver, "PLATFORMS", [PLATFORM])

    class _SoftNotFoundBrowser(_StubBrowser):
        async def new_page(self):
            return _Page(html=NOT_FOUND_HTML)

    monkeypatch.setattr(resolver, "StealthBrowser", _SoftNotFoundBrowser)

    asyncio.run(resolver.build_discovery_tree(target.pk, _pacer()))

    assert DiscoveredAccount.objects.filter(target=target).count() == 0
