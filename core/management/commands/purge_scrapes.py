"""Clear the stored raw text and metadata for a target."""

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from core.exceptions import PersonaliTreeError
from core.models import Target
from core.scraper.retention import purge_target_scrapes


class Command(BaseCommand):
    help = "Clear the stored raw text and metadata of a target's scrapes."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("target_id", type=int)

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            target = Target.objects.fetch(options["target_id"])
        except PersonaliTreeError as exc:
            raise CommandError(str(exc)) from exc

        purged = purge_target_scrapes(target.pk)
        self.stdout.write(f"Purged {purged} scrape(s) for target {target.pk}")
