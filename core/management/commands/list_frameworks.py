"""List the loaded instruments and what they contain."""

from typing import Any

from django.core.management.base import BaseCommand

from core.models import Framework


class Command(BaseCommand):
    help = "List the loaded instruments, their traits and their item counts."

    def handle(self, *args: Any, **options: Any) -> None:
        frameworks = Framework.objects.order_by("slug")
        if not frameworks.exists():
            self.stdout.write("No instruments loaded; run load_questionnaire first")
            return

        for framework in frameworks:
            state = "active" if framework.is_active else "inactive"
            self.stdout.write(
                f"{framework.slug}  {framework.name}  "
                f"[{state}]  traits={framework.traits.count()}  "
                f"items={framework.questions.count()}"
            )
            if framework.citation:
                self.stdout.write(f"    {framework.citation}")
