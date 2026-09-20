"""
Aggregates questionnaire answers into per-trait instrument scores.
"""

import logging

from core.exceptions import QuestionnaireError
from core.models import (
    Framework,
    ProfileResult,
    Question,
    QuestionnaireResponse,
    Target,
)

logger = logging.getLogger(__name__)


def calculate_framework_scores(target: Target, framework: Framework) -> None:
    """Average the target's answers into one entry per trait of the instrument."""
    traits = list(framework.traits.all())
    if not traits:
        raise QuestionnaireError(f"{framework.slug} declares no traits to score")

    totals: dict[int, int] = {}
    counts: dict[int, int] = {}
    responses = QuestionnaireResponse.objects.filter(
        target=target,
        question__framework=framework,
    ).select_related("question")

    for response in responses:
        trait_id = response.question.trait_id
        totals[trait_id] = totals.get(trait_id, 0) + _scored(
            response.question,
            response.score,
        )
        counts[trait_id] = counts.get(trait_id, 0) + 1

    score_data = {
        trait.slug: {
            "name": trait.name,
            "average": (
                totals[trait.id] / counts[trait.id] if counts.get(trait.id) else None
            ),
            "answers": counts.get(trait.id, 0),
        }
        for trait in traits
    }

    ProfileResult.objects.update_or_create(
        target=target,
        framework=framework,
        defaults={"score_data": score_data},
    )
    logger.info(
        "Scored %s for %s from %d answers",
        framework.slug,
        target.seed_username,
        sum(counts.values()),
    )


def _scored(question: Question, score: int) -> int:
    """Return the answer, flipping it when the item is reverse scored."""
    if not question.reverse_scored:
        return score
    return question.min_score + question.max_score - score
