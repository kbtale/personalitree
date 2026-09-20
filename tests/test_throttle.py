import asyncio
import time

from core.scraper import throttle
from core.scraper.throttle import HostPacer, fetch


class _Response:
    def __init__(self, status: int, headers: dict[str, str] | None = None):
        self.status = status
        self.headers = headers or {}


class _Page:
    def __init__(self, responses):
        self._responses = list(responses)
        self.urls: list[str] = []

    async def goto(self, url, **kwargs):
        self.urls.append(url)
        if not self._responses:
            return None
        return self._responses.pop(0)


def _pacer(**overrides) -> HostPacer:
    options = {"delay": 0.0, "concurrency": 1, "budget": 10, "retries": 0}
    options.update(overrides)
    return HostPacer(**options)


def test_host_of_ignores_path_and_query():
    assert HostPacer.host_of("https://github.com/seed_user?tab=1") == "github.com"


def test_budget_stops_requests_once_it_is_spent():
    pacer = _pacer(budget=2)

    allowed = [asyncio.run(pacer.wait("github.com")) for _ in range(3)]

    assert allowed == [True, True, False]
    assert pacer.requests_made("github.com") == 3


def test_delay_spaces_out_two_requests():
    pacer = _pacer(delay=0.05)
    asyncio.run(pacer.wait("github.com"))

    started = time.monotonic()
    asyncio.run(pacer.wait("github.com"))

    assert time.monotonic() - started >= 0.05


def test_back_off_delays_the_next_request():
    pacer = _pacer()
    asyncio.run(pacer.wait("github.com"))

    pacer.back_off("github.com", 0.15)
    started = time.monotonic()
    asyncio.run(pacer.wait("github.com"))

    assert time.monotonic() - started >= 0.15


def test_back_off_without_a_retry_after_header_uses_the_default(monkeypatch):
    monkeypatch.setattr(throttle, "DEFAULT_RATE_LIMIT_BACKOFF_SECONDS", 0.1)
    pacer = _pacer()
    asyncio.run(pacer.wait("github.com"))

    pacer.back_off("github.com", None)
    started = time.monotonic()
    asyncio.run(pacer.wait("github.com"))

    assert time.monotonic() - started >= 0.1


def test_rate_limited_statuses_are_recognised():
    assert HostPacer.is_rate_limited(_Response(429))
    assert HostPacer.is_rate_limited(_Response(503))
    assert not HostPacer.is_rate_limited(_Response(200))
    assert not HostPacer.is_rate_limited(None)


def test_retry_after_is_read_only_when_numeric():
    assert HostPacer.retry_after_seconds(_Response(429, {"retry-after": "5"})) == 5.0
    assert HostPacer.retry_after_seconds(_Response(429)) is None

    http_date = {"retry-after": "Wed, 21 Oct 2026 07:28:00 GMT"}
    assert HostPacer.retry_after_seconds(_Response(429, http_date)) is None


def test_fetch_returns_the_first_accepted_response():
    page = _Page([_Response(200)])
    pacer = _pacer()

    response = asyncio.run(fetch(page, "https://github.com/seed_user", pacer))

    assert response is not None
    assert response.status == 200
    assert page.urls == ["https://github.com/seed_user"]


def test_fetch_retries_once_after_a_rate_limit():
    page = _Page([_Response(429, {"retry-after": "0"}), _Response(200)])
    pacer = _pacer(retries=1)

    response = asyncio.run(fetch(page, "https://github.com/seed_user", pacer))

    assert response is not None
    assert response.status == 200
    assert len(page.urls) == 2


def test_fetch_gives_up_after_the_retry_budget():
    page = _Page([_Response(429, {"retry-after": "0"}), _Response(429)])
    pacer = _pacer(retries=1)

    response = asyncio.run(fetch(page, "https://github.com/seed_user", pacer))

    assert response is not None
    assert response.status == 429
    assert len(page.urls) == 2


def test_fetch_skips_the_request_when_the_budget_is_spent():
    page = _Page([_Response(200)])
    pacer = _pacer(budget=0)

    assert asyncio.run(fetch(page, "https://github.com/seed_user", pacer)) is None
    assert page.urls == []
