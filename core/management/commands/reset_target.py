"""Reset a target so it can be scraped again."""

from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from core.exceptions import PersonaliTreeError
from core.models import Target


class Command(BaseCommand):
    help = "Reset a target to PENDING and clear its attempt history."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("target_id", type=int)

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            target = Target.objects.fetch(options["target_id"])
        except PersonaliTreeError as exc:
            raise CommandError(str(exc)) from exc

        Target.objects.filter(id=target.pk).update(
            status=Target.Status.PENDING,
            attempts=0,
            last_error="",
        )
        self.stdout.write(f"Target {target.pk} reset to pending")
