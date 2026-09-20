import pytest

from core.exceptions import TargetAlreadyQueuedError
from core.models import Target
from core.scraper import queue

pytestmark = pytest.mark.django_db


def test_enqueue_rejects_a_target_that_is_already_active(monkeypatch):
    target = Target.objects.create(
        seed_username="seed_user",
        status=Target.Status.SCRAPING,
    )
    dispatched: list[tuple] = []
    monkeypatch.setattr(
        queue, "async_task", lambda *args, **kwargs: dispatched.append(args)
    )

    with pytest.raises(TargetAlreadyQueuedError):
        queue.enqueue_scrape(target)

    assert dispatched == []


def test_enqueue_marks_the_target_queued_and_dispatches_the_task(monkeypatch):
    target = Target.objects.create(seed_username="seed_user")
    dispatched: list[tuple] = []

    def _async_task(func, *args, **kwargs):
        dispatched.append((func, args, kwargs))
        return "task-id"

    monkeypatch.setattr(queue, "async_task", _async_task)

    task_id = queue.enqueue_scrape(target)

    assert task_id == "task-id"
    target.refresh_from_db()
    assert target.status == Target.Status.QUEUED
    func, args, kwargs = dispatched[0]
    assert func == queue.SCRAPE_TASK
    assert args == (target.pk,)
    assert kwargs["task_name"] == f"scrape-target-{target.pk}"
    assert kwargs["q_options"] == queue.SCRAPE_TASK_OPTIONS
