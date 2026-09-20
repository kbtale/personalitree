"""Load one instrument (framework, traits and items) from a JSON file."""

import json
from pathlib import Path
from typing import Any

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError, CommandParser
from django.db import transaction

from core.constants import SCORE_MAX, SCORE_MIN
from core.models import Framework, Question, Trait

FRAMEWORK_FIELDS = (
    "slug",
    "name",
    "description",
    "citation",
    "source_url",
    "is_active",
)
FRAMEWORK_REQUIRED = ("slug", "name")
TRAIT_FIELDS = ("slug", "name", "description")
TRAIT_REQUIRED = ("slug", "name")
ITEM_FIELDS = ("id", "trait", "text", "reverse_scored", "min_score", "max_score")
ITEM_REQUIRED = ("id", "trait", "text")


class Command(BaseCommand):
    help = "Load one instrument from a JSON file; the file is the source of truth."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("path", type=Path)

    def handle(self, *args: Any, **options: Any) -> None:
        document = self._read_document(options["path"])
        framework_values = self._fields(
            document.get("framework"),
            "framework",
            FRAMEWORK_REQUIRED,
            FRAMEWORK_FIELDS,
        )
        traits = [
            self._fields(item, f"traits[{index}]", TRAIT_REQUIRED, TRAIT_FIELDS)
            for index, item in enumerate(self._list(document, "traits"))
        ]
        items = [
            self._fields(item, f"items[{index}]", ITEM_REQUIRED, ITEM_FIELDS)
            for index, item in enumerate(self._list(document, "items"))
        ]
        self._validate(traits, items)

        with transaction.atomic():
            framework = self._save_framework(framework_values)
            traits_created, traits_updated = self._save_traits(framework, traits)
            items_created, items_updated, items_removed, items_kept = self._save_items(
                framework,
                items,
            )

        self.stdout.write(
            f"{framework.slug}: {traits_created + traits_updated} traits, "
            f"{items_created} items created, {items_updated} updated"
        )
        if items_removed:
            self.stdout.write(f"Removed {items_removed} item(s) absent from the file")
        if items_kept:
            self.stdout.write(f"Kept {items_kept} item(s) that already have answers")

    def _read_document(self, path: Path) -> dict[str, Any]:
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise CommandError(f"cannot read {path}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise CommandError(f"{path} is not valid JSON: {exc}") from exc

        if not isinstance(document, dict):
            raise CommandError(f"{path} must contain a JSON object")
        return document

    def _list(self, document: dict[str, Any], key: str) -> list[Any]:
        value = document.get(key)
        if not isinstance(value, list) or not value:
            raise CommandError(f"'{key}' must be a non-empty list")
        return value

    def _fields(
        self,
        item: Any,
        label: str,
        required: tuple[str, ...],
        allowed: tuple[str, ...],
    ) -> dict[str, Any]:
        if not isinstance(item, dict):
            raise CommandError(f"{label} must be an object")

        missing = [field for field in required if not item.get(field)]
        if missing:
            raise CommandError(f"{label} is missing {', '.join(missing)}")

        unknown = sorted(field for field in item if field not in allowed)
        if unknown:
            raise CommandError(f"{label} has unknown field(s): {', '.join(unknown)}")

        return {field: item[field] for field in allowed if field in item}

    def _validate(
        self,
        traits: list[dict[str, Any]],
        items: list[dict[str, Any]],
    ) -> None:
        slugs = [trait["slug"] for trait in traits]
        duplicates = sorted({slug for slug in slugs if slugs.count(slug) > 1})
        if duplicates:
            raise CommandError(f"duplicate trait slugs: {', '.join(duplicates)}")

        unknown = sorted({item["trait"] for item in items} - set(slugs))
        if unknown:
            raise CommandError(
                f"items reference undeclared traits: {', '.join(unknown)}"
            )

        ids = [item["id"] for item in items]
        repeated = sorted({item_id for item_id in ids if ids.count(item_id) > 1})
        if repeated:
            raise CommandError(f"duplicate item ids: {', '.join(repeated)}")

        for item in items:
            low = item.get("min_score", SCORE_MIN)
            high = item.get("max_score", SCORE_MAX)
            if low >= high:
                raise CommandError(f"item {item['id']} has min_score >= max_score")

    def _save_framework(self, values: dict[str, Any]) -> Framework:
        framework, _ = Framework.objects.update_or_create(
            slug=values["slug"],
            defaults={key: value for key, value in values.items() if key != "slug"},
        )
        return framework

    def _save_traits(
        self,
        framework: Framework,
        traits: list[dict[str, Any]],
    ) -> tuple[int, int]:
        created = 0
        updated = 0
        for values in traits:
            _, was_created = Trait.objects.update_or_create(
                framework=framework,
                slug=values["slug"],
                defaults={key: value for key, value in values.items() if key != "slug"},
            )
            created += int(was_created)
            updated += int(not was_created)
        return created, updated

    def _save_items(
        self,
        framework: Framework,
        items: list[dict[str, Any]],
    ) -> tuple[int, int, int, int]:
        traits = {trait.slug: trait for trait in framework.traits.all()}
        created = 0
        updated = 0
        kept: list[str] = []

        for values in items:
            question, was_created = Question.objects.update_or_create(
                framework=framework,
                question_id=values["id"],
                defaults={
                    "trait": traits[values["trait"]],
                    "text": values["text"],
                    "reverse_scored": values.get("reverse_scored", False),
                    "min_score": values.get("min_score", SCORE_MIN),
                    "max_score": values.get("max_score", SCORE_MAX),
                },
            )
            try:
                question.full_clean(validate_unique=False)
            except ValidationError as exc:
                raise CommandError(
                    f"item {values['id']} is invalid: {exc.message_dict}"
                ) from exc
            kept.append(question.question_id)
            created += int(was_created)
            updated += int(not was_created)

        stale = framework.questions.exclude(question_id__in=kept)
        with_answers = stale.filter(responses__isnull=False).count()
        removed = stale.filter(responses__isnull=True).delete()[0]
        return created, updated, removed, with_answers
