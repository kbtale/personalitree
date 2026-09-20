"""Run one scrape attempt in the foreground, without the queue."""

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from core.exceptions import PersonaliTreeError
from core.models import Target
from core.scraper.tasks import run_target_inline


class Command(BaseCommand):
    help = "Run one scrape attempt now, in this process."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("target_id", type=int)

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            target = Target.objects.fetch(options["target_id"])
        except PersonaliTreeError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(f"Running target {target.pk} ({target.seed_username})")
        run_target_inline(target.pk)

        target.refresh_from_db()
        self.stdout.write(
            f"Target {target.pk} is {target.status} after {target.attempts} attempt(s)"
        )
        if target.last_error:
            self.stderr.write(target.last_error)
