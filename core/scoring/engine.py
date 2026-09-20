"""
Aggregates questionnaire answers into framework scores.
"""

import logging

from core.constants import FRAMEWORK_TRAITS, Framework
from core.exceptions import QuestionnaireError
from core.models import ProfileResult, Question, QuestionnaireResponse, Target

logger = logging.getLogger(__name__)


def calculate_framework_scores(
    target: Target,
    framework_name: str = Framework.BIG_FIVE,
) -> None:
    """Average the target's answers into one score per framework trait."""
    traits = FRAMEWORK_TRAITS.get(framework_name)
    if traits is None:
        raise QuestionnaireError(f"unknown framework {framework_name}")

    totals: dict[str, int] = {}
    counts: dict[str, int] = {}
    responses = QuestionnaireResponse.objects.filter(target=target).select_related(
        "question"
    )
    for response in responses:
        trait = response.question.trait
        if trait not in traits:
            continue
        totals[trait] = totals.get(trait, 0) + _scored(
            response.question, response.score
        )
        counts[trait] = counts.get(trait, 0) + 1

    scores: dict[str, float | None] = {
        trait: totals[trait] / counts[trait] if counts.get(trait) else None
        for trait in traits
    }

    ProfileResult.objects.update_or_create(
        target=target,
        framework_name=framework_name,
        defaults={"score_data": scores},
    )
    logger.info(
        "Calculated %s scores for %s from %d answers",
        framework_name,
        target.seed_username,
        sum(counts.values()),
    )


def _scored(question: Question, score: int) -> int:
    """Return the answer, flipping it when the item is reverse scored."""
    if not question.reverse_scored:
        return score
    return question.min_score + question.max_score - score
