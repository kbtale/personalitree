"""List the targets and where they stand."""

from typing import Any

from django.core.management.base import BaseCommand

from core.models import Target


class Command(BaseCommand):
    help = "List the targets with their status, attempts and last error."

    def handle(self, *args: Any, **options: Any) -> None:
        targets = Target.objects.order_by("-created_at")
        if not targets.exists():
            self.stdout.write("No targets yet; add one with add_target <username>")
            return

        for target in targets:
            created = target.created_at.strftime("%Y-%m-%d %H:%M")
            self.stdout.write(
                f"{target.pk}  {target.seed_username}  {target.status}  "
                f"attempts={target.attempts}  created={created}"
            )
            if target.last_error:
                self.stdout.write(f"    last error: {target.last_error}")
