"""Load a question bank from a JSON file."""

import json
from pathlib import Path
from typing import Any

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError, CommandParser

from core.models import Question

REQUIRED_FIELDS = ("question_id", "framework_name", "trait", "text")
OPTIONAL_FIELDS = ("reverse_scored", "min_score", "max_score")


class Command(BaseCommand):
    help = "Load or update questionnaire items from a JSON file."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("path", type=Path)

    def handle(self, *args: Any, **options: Any) -> None:
        path: Path = options["path"]
        items = self._read_items(path)

        created = 0
        updated = 0
        for index, item in enumerate(items):
            question = self._build_question(item, index)
            _, was_created = Question.objects.update_or_create(
                framework_name=question.framework_name,
                question_id=question.question_id,
                defaults={
                    "trait": question.trait,
                    "text": question.text,
                    "reverse_scored": question.reverse_scored,
                    "min_score": question.min_score,
                    "max_score": question.max_score,
                },
            )
            created += int(was_created)
            updated += int(not was_created)

        self.stdout.write(f"Questions loaded: {created} created, {updated} updated")

    def _read_items(self, path: Path) -> list[Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise CommandError(f"cannot read {path}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise CommandError(f"{path} is not valid JSON: {exc}") from exc

        if not isinstance(payload, list):
            raise CommandError(f"{path} must contain a JSON array of items")
        return payload

    def _build_question(self, item: Any, index: int) -> Question:
        if not isinstance(item, dict):
            raise CommandError(f"item {index} is not an object")

        missing = [field for field in REQUIRED_FIELDS if field not in item]
        if missing:
            raise CommandError(f"item {index} is missing {', '.join(missing)}")

        known = {
            field: item[field]
            for field in (*REQUIRED_FIELDS, *OPTIONAL_FIELDS)
            if field in item
        }
        question = Question(**known)
        try:
            question.full_clean(validate_unique=False)
        except ValidationError as exc:
            raise CommandError(f"item {index} is invalid: {exc.message_dict}") from exc
        return question
