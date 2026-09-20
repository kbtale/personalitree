import asyncio

import pytest

from core.constants import MAX_SCRAPE_ATTEMPTS
from core.exceptions import PersonaliTreeError
from core.models import Target
from core.scraper import queue, tasks

pytestmark = pytest.mark.django_db(transaction=True)


def _stub_dispatch(monkeypatch) -> list[tuple]:
    dispatched: list[tuple] = []

    def _async_task(func, *args, **kwargs):
        dispatched.append((func, args, kwargs))

    monkeypatch.setattr(queue, "async_task", _async_task)
    return dispatched


def test_successful_run_completes_the_target(monkeypatch):
    target = Target.objects.create(seed_username="seed_user")

    async def _pipeline(target_id: int) -> None:
        await asyncio.to_thread(_mark_completed, target_id)

    monkeypatch.setattr(tasks, "_run_pipeline", _pipeline)

    tasks.scrape_target(target.pk)

    target.refresh_from_db()
    assert target.status == Target.Status.COMPLETED
    assert target.attempts == 1
    assert target.last_error == ""


def test_first_failure_requeues_the_target(monkeypatch):
    target = Target.objects.create(seed_username="seed_user")
    dispatched = _stub_dispatch(monkeypatch)

    async def _pipeline(target_id: int) -> None:
        raise PersonaliTreeError("platform unreachable")

    monkeypatch.setattr(tasks, "_run_pipeline", _pipeline)

    tasks.scrape_target(target.pk)

    target.refresh_from_db()
    assert target.attempts == 1
    assert target.status == Target.Status.QUEUED
    assert target.last_error == ""
    assert len(dispatched) == 1
    assert dispatched[0][1] == (target.pk,)


def test_failure_after_the_attempt_cap_marks_the_target_failed(monkeypatch):
    target = Target.objects.create(
        seed_username="seed_user",
        status=Target.Status.SCRAPING,
    )
    Target.objects.filter(id=target.pk).update(attempts=MAX_SCRAPE_ATTEMPTS - 1)
    dispatched = _stub_dispatch(monkeypatch)

    async def _pipeline(target_id: int) -> None:
        raise PersonaliTreeError("every platform was blocked")

    monkeypatch.setattr(tasks, "_run_pipeline", _pipeline)

    tasks.scrape_target(target.pk)

    target.refresh_from_db()
    assert target.attempts == MAX_SCRAPE_ATTEMPTS
    assert target.status == Target.Status.FAILED
    assert target.last_error == "every platform was blocked"
    assert dispatched == []


def test_unexpected_errors_are_not_swallowed(monkeypatch):
    target = Target.objects.create(seed_username="seed_user")
    dispatched = _stub_dispatch(monkeypatch)

    async def _pipeline(target_id: int) -> None:
        raise RuntimeError("programming error")

    monkeypatch.setattr(tasks, "_run_pipeline", _pipeline)

    with pytest.raises(RuntimeError):
        tasks.scrape_target(target.pk)

    target.refresh_from_db()
    assert target.status == Target.Status.SCRAPING
    assert dispatched == []


def _mark_completed(target_id: int) -> None:
    Target.objects.filter(id=target_id).update(status=Target.Status.COMPLETED)
