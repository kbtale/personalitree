from django.core.management import call_command
from django.core.management.base import CommandError
import pytest

from core.constants import ConfigKey, RetentionMode
from core.exceptions import PersonaliTreeError
from core.models import RawScrape, Target
from core.scraper import retention, tasks

pytestmark = pytest.mark.django_db


def _add_scrape(target: Target, text: str = "profile text") -> RawScrape:
    return RawScrape.objects.create(
        target=target,
        platform_name="github",
        raw_text_dump=text,
        metadata_json={"title": "profile"},
    )


def test_ephemeral_mode_clears_the_raw_text(monkeypatch, target):
    monkeypatch.setenv(ConfigKey.RETENTION_MODE, RetentionMode.EPHEMERAL)
    scrape = _add_scrape(target)

    retention.apply_retention(target.pk)

    scrape.refresh_from_db()
    assert scrape.raw_text_dump == ""
    assert scrape.metadata_json == {}


def test_persistent_mode_keeps_the_raw_text(monkeypatch, target):
    monkeypatch.setenv(ConfigKey.RETENTION_MODE, RetentionMode.PERSISTENT)
    scrape = _add_scrape(target)

    retention.apply_retention(target.pk)

    scrape.refresh_from_db()
    assert scrape.raw_text_dump == "profile text"


def test_unset_mode_keeps_the_raw_text(monkeypatch, target):
    monkeypatch.delenv(ConfigKey.RETENTION_MODE, raising=False)
    scrape = _add_scrape(target)

    retention.apply_retention(target.pk)

    scrape.refresh_from_db()
    assert scrape.raw_text_dump == "profile text"


def test_purge_only_touches_the_requested_target(target):
    other = Target.objects.create(seed_username="other_user")
    mine = _add_scrape(target)
    theirs = _add_scrape(other)

    purged = retention.purge_target_scrapes(target.pk)

    assert purged == 1
    mine.refresh_from_db()
    theirs.refresh_from_db()
    assert mine.raw_text_dump == ""
    assert theirs.raw_text_dump == "profile text"


def test_successful_ephemeral_run_purges_the_text(monkeypatch, target):
    monkeypatch.setenv(ConfigKey.RETENTION_MODE, RetentionMode.EPHEMERAL)
    scrape = _add_scrape(target)

    async def _pipeline(target_id: int) -> None:
        return None

    monkeypatch.setattr(tasks, "_run_pipeline", _pipeline)

    tasks.scrape_target(target.pk)

    scrape.refresh_from_db()
    assert scrape.raw_text_dump == ""


def test_failed_ephemeral_run_also_purges_the_text(monkeypatch, target):
    monkeypatch.setenv(ConfigKey.RETENTION_MODE, RetentionMode.EPHEMERAL)
    scrape = _add_scrape(target)

    async def _pipeline(target_id: int) -> None:
        raise PersonaliTreeError("platform unreachable")

    monkeypatch.setattr(tasks, "_run_pipeline", _pipeline)

    tasks.scrape_target(target.pk)

    scrape.refresh_from_db()
    assert scrape.raw_text_dump == ""


def test_purge_scrapes_command_clears_the_text(target):
    _add_scrape(target)

    call_command("purge_scrapes", target.pk)

    assert RawScrape.objects.get(target=target).raw_text_dump == ""


def test_purge_scrapes_reports_a_missing_target():
    with pytest.raises(CommandError):
        call_command("purge_scrapes", 4321)
