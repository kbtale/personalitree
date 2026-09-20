from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
import pytest

from core.models import Target
from core.scraper import queue

pytestmark = pytest.mark.django_db


def test_queue_scrape_dispatches_the_task(monkeypatch):
    target = Target.objects.create(seed_username="seed_user")
    monkeypatch.setattr(queue, "async_task", lambda *args, **kwargs: "task-id")
    stdout = StringIO()

    call_command("queue_scrape", target.pk, stdout=stdout)

    target.refresh_from_db()
    assert target.status == Target.Status.QUEUED
    assert "task-id" in stdout.getvalue()


def test_queue_scrape_reports_a_missing_target():
    with pytest.raises(CommandError):
        call_command("queue_scrape", 4321)


def test_queue_scrape_refuses_a_target_that_is_already_active(monkeypatch):
    target = Target.objects.create(
        seed_username="seed_user",
        status=Target.Status.SCRAPING,
    )
    monkeypatch.setattr(queue, "async_task", lambda *args, **kwargs: "task-id")

    with pytest.raises(CommandError):
        call_command("queue_scrape", target.pk)


def test_reset_target_clears_the_attempt_history():
    target = Target.objects.create(
        seed_username="seed_user",
        status=Target.Status.FAILED,
    )
    Target.objects.filter(id=target.pk).update(
        attempts=2,
        last_error="every platform was blocked",
    )
    stdout = StringIO()

    call_command("reset_target", target.pk, stdout=stdout)

    target.refresh_from_db()
    assert target.status == Target.Status.PENDING
    assert target.attempts == 0
    assert target.last_error == ""
    assert "reset" in stdout.getvalue()
