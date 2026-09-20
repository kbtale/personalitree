"""Queue the scraping pipeline for a target."""

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from core.exceptions import PersonaliTreeError
from core.models import Target
from core.scraper.queue import enqueue_scrape


class Command(BaseCommand):
    help = "Queue the scraping pipeline for a target id."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("target_id", type=int)

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            target = Target.objects.fetch(options["target_id"])
            task_id = enqueue_scrape(target)
        except PersonaliTreeError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(f"Queued task {task_id} for target {target.pk}")
