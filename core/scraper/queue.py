"""Queueing for the scraping pipeline."""

import logging
from typing import Any

from django_q.tasks import async_task

from core.constants import SCRAPE_TASK_TIMEOUT_SECONDS
from core.exceptions import TargetAlreadyQueuedError
from core.models import Target

logger = logging.getLogger(__name__)

SCRAPE_TASK = "core.scraper.tasks.scrape_target"

SCRAPE_TASK_OPTIONS: dict[str, Any] = {
    "save": True,
    "ack_failure": True,
    "timeout": SCRAPE_TASK_TIMEOUT_SECONDS,
}

ACTIVE_STATUSES = (
    Target.Status.QUEUED,
    Target.Status.SCRAPING,
    Target.Status.EVALUATING,
)


def enqueue_scrape(target: Target) -> str:
    """Queue the scraping pipeline for a target and return the task id."""
    if target.status in ACTIVE_STATUSES:
        raise TargetAlreadyQueuedError(f"Target {target.pk} is already {target.status}")

    Target.objects.filter(id=target.pk).update(status=Target.Status.QUEUED)
    task_id = async_task(
        SCRAPE_TASK,
        target.pk,
        task_name=f"scrape-target-{target.pk}",
        q_options=SCRAPE_TASK_OPTIONS,
    )
    logger.info("Queued scrape task %s for target %s", task_id, target.pk)
    return task_id
