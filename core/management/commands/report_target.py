"""Print everything recorded about one target and its profiles."""

import json
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from core.exceptions import PersonaliTreeError
from core.models import Framework, ProfileResult, Target
from core.scoring.type_code import letter, scale_midpoint, type_code


class Command(BaseCommand):
    help = "Report on one target: status, instruments, scores and discovered accounts."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("target_id", type=int)
        parser.add_argument(
            "--json",
            action="store_true",
            help="Print the payload as JSON instead of a readable summary.",
        )
        parser.add_argument(
            "--out",
            type=Path,
            default=None,
            help="Also write the printed output to this file.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        try:
            target = Target.objects.fetch(options["target_id"])
        except PersonaliTreeError as exc:
            raise CommandError(str(exc)) from exc

        payload = build_payload(target)
        rendered = (
            json.dumps(payload, indent=2) if options["json"] else render_text(payload)
        )
        self.stdout.write(rendered)

        if options["out"]:
            Path(options["out"]).write_text(rendered + "\n", encoding="utf-8")
            self.stderr.write(f"Written to {options['out']}")


def build_payload(target: Target) -> dict[str, Any]:
    """Everything known about the target, in the shape the report prints."""
    results = {
        result.framework.slug: result
        for result in target.profile_results.select_related("framework")
    }
    instruments = [
        _instrument(framework, results.get(framework.slug))
        for framework in Framework.objects.order_by("slug")
    ]

    accounts = [
        {
            "platform": account.platform_name,
            "username": account.username,
            "display_name": account.display_name,
            "url": account.url,
            "confidence": account.confidence,
            "signals": account.signals,
        }
        for account in target.discovered_accounts.order_by("platform_name")
    ]

    return {
        "target": {
            "id": target.pk,
            "username": target.seed_username,
            "status": target.status,
            "attempts": target.attempts,
            "last_error": target.last_error,
            "created_at": target.created_at.isoformat(),
        },
        "instruments": instruments,
        "accounts": accounts,
    }


def _instrument(
    framework: Framework,
    result: ProfileResult | None,
) -> dict[str, Any]:
    """One instrument's entry, with the letters its traits read as."""
    scores = result.score_data if result else {}
    traits = list(framework.traits.all())
    midpoint = scale_midpoint(framework)
    labels: dict[str, str | None] = {}
    if midpoint is not None:
        for trait in traits:
            average = (scores.get(trait.slug) or {}).get("average")
            labels[trait.slug] = letter(trait, average, midpoint)

    return {
        "slug": framework.slug,
        "name": framework.name,
        "citation": framework.citation,
        "source_url": framework.source_url,
        "is_active": framework.is_active,
        "evaluated": result is not None,
        "type": type_code(framework, scores),
        "type_declared": bool(traits)
        and all(trait.high_label and trait.low_label for trait in traits),
        "traits": _annotate(scores, labels),
    }


def _annotate(
    scores: dict[str, Any],
    labels: dict[str, str | None],
) -> dict[str, Any]:
    """The trait entries, each carrying the letter it reads as when there is one."""
    annotated = {}
    for slug, score in scores.items():
        entry = dict(score)
        if labels.get(slug):
            entry["label"] = labels[slug]
        annotated[slug] = entry
    return annotated


def _type_lines(instrument: dict[str, Any]) -> list[str]:
    """The type line: the code, why it is missing, or nothing at all."""
    if instrument["type"]:
        return [f"    type: {instrument['type']}"]
    if not instrument["type_declared"]:
        return []
    unanswered = sum(
        1 for score in instrument["traits"].values() if score["average"] is None
    )
    return [f"    type: unavailable - {unanswered} trait(s) have no answers"]


def render_text(payload: dict[str, Any]) -> str:
    """A terminal-readable rendering of the payload."""
    target = payload["target"]
    lines = [
        f"Target {target['id']}: {target['username']}",
        f"  status      {target['status']} after {target['attempts']} attempt(s)",
        f"  created     {target['created_at']}",
    ]
    if target["last_error"]:
        lines.append(f"  last error  {target['last_error']}")

    lines.append("Instruments")
    for instrument in payload["instruments"]:
        state = "active" if instrument["is_active"] else "inactive"
        lines.append(f"  {instrument['slug']} ({state}) - {instrument['name']}")
        if instrument["citation"]:
            lines.append(f"    cite: {instrument['citation']}")
        if not instrument["evaluated"]:
            lines.append("    not evaluated")
            continue
        for score in instrument["traits"].values():
            average = score["average"]
            shown = "no answers" if average is None else f"{average:.2f}"
            label = f" [{score['label']}]" if score.get("label") else ""
            lines.append(
                f"    {score['name']}: {shown} ({score['answers']} answer(s)){label}"
            )
        lines.extend(_type_lines(instrument))

    lines.append("Discovered accounts")
    if not payload["accounts"]:
        lines.append("  none")
    for account in payload["accounts"]:
        signals = ", ".join(account["signals"]) or "existence only"
        lines.append(
            f"  {account['platform']}/{account['username']}  "
            f"confidence {account['confidence']:.2f}  [{signals}]"
        )
        lines.append(f"    {account['url']}")

    return "\n".join(lines)
