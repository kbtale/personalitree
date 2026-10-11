"""Reads the type letters an instrument's trait scores add up to."""

from typing import Any

from core.models import Framework, Trait


def scale_midpoint(framework: Framework) -> float | None:
    """The middle of the scale the framework's items declare, or None without items."""
    ranges = list(framework.questions.values_list("min_score", "max_score"))
    if not ranges:
        return None
    return (min(low for low, _ in ranges) + max(high for _, high in ranges)) / 2


def letter(trait: Trait, average: float | None, midpoint: float) -> str | None:
    """The side a trait's average lands on, or None when the trait cannot be read."""
    if average is None or not trait.high_label or not trait.low_label:
        return None
    return trait.high_label if average > midpoint else trait.low_label


def type_code(framework: Framework, score_data: dict[str, Any]) -> str | None:
    """Every trait's letter joined in order, or None when any trait is unreadable."""
    traits = list(framework.traits.all())
    midpoint = scale_midpoint(framework)
    if not traits or midpoint is None:
        return None

    letters = [
        letter(trait, (score_data.get(trait.slug) or {}).get("average"), midpoint)
        for trait in traits
    ]
    if any(value is None for value in letters):
        return None
    return "".join(value for value in letters if value is not None)
