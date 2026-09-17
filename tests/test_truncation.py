from datetime import timedelta

from django.utils import timezone
import pytest

from core.models import RawScrape, Target
from core.scraper import truncation

pytestmark = pytest.mark.django_db


def _set_config(monkeypatch, **values):
    def _get_config(key: str, default: str) -> str:
        return values.get(key, default)

    monkeypatch.setattr(truncation, "get_config", _get_config)


def _add_scrape(target: Target, platform_name: str, raw_text: str) -> RawScrape:
    return RawScrape.objects.create(
        target=target,
        platform_name=platform_name,
        raw_text_dump=raw_text,
    )


def test_payload_contains_platform_header_and_text(monkeypatch, target):
    _set_config(monkeypatch)
    _add_scrape(target, "github", "hello")

    assert truncation.prepare_llm_payload(target.id) == "[github]\nhello"


def test_blank_scrapes_are_skipped(monkeypatch, target):
    _set_config(monkeypatch)
    _add_scrape(target, "github", "   ")

    assert truncation.prepare_llm_payload(target.id) == ""


def test_newest_scrapes_are_listed_first(monkeypatch, target):
    _set_config(monkeypatch)
    older = _add_scrape(target, "github", "old text")
    _add_scrape(target, "reddit", "new text")
    RawScrape.objects.filter(pk=older.pk).update(
        scraped_at=timezone.now() - timedelta(hours=1)
    )

    payload = truncation.prepare_llm_payload(target.id)

    assert payload.startswith("[reddit]\nnew text")


def test_max_posts_caps_the_number_of_scrapes(monkeypatch, target):
    _set_config(monkeypatch, MAX_SCRAPE_POSTS="1")
    _add_scrape(target, "github", "first")
    _add_scrape(target, "reddit", "second")

    assert truncation.prepare_llm_payload(target.id) == "[reddit]\nsecond"


def test_scrapes_outside_the_timeframe_are_dropped(monkeypatch, target):
    _set_config(monkeypatch, SCRAPE_TIMEFRAME_MONTHS="1")
    old = _add_scrape(target, "github", "ancient")
    RawScrape.objects.filter(pk=old.pk).update(
        scraped_at=timezone.now() - timedelta(days=60)
    )

    assert truncation.prepare_llm_payload(target.id) == ""


def test_payload_is_truncated_to_the_token_budget(monkeypatch, target):
    _set_config(monkeypatch, MAX_LLM_TOKENS="2")
    _add_scrape(target, "github", "x" * 100)

    assert len(truncation.prepare_llm_payload(target.id)) == 8
