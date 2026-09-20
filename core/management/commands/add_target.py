"""Add a target to investigate."""

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from core.models import Target

ACTIVE_STATUSES = (
    Target.Status.QUEUED,
    Target.Status.SCRAPING,
    Target.Status.EVALUATING,
)


class Command(BaseCommand):
    help = "Add a username to investigate; every active instrument is evaluated for it."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("username")

    def handle(self, *args: Any, **options: Any) -> None:
        username = options["username"].strip()
        if not username:
            raise CommandError("a username is required")

        running = Target.objects.filter(
            seed_username=username,
            status__in=ACTIVE_STATUSES,
        ).exists()
        if running:
            raise CommandError(f"target '{username}' already has a run in flight")

        target = Target.objects.create(seed_username=username)
        self.stdout.write(
            f"Added target {target.pk} for '{username}' "
            "(run it with run_target or queue_scrape)"
        )
