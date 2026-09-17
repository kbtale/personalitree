"""
Shell for calculating personality framework scores from raw AI answers.
"""

import logging

from core.models import ProfileResult, QuestionnaireResponse, Target

logger = logging.getLogger(__name__)


def calculate_framework_scores(target: Target) -> None:
    _calculate_big_five(target)


def _calculate_big_five(target: Target) -> None:
    responses = QuestionnaireResponse.objects.filter(target=target)
    if not responses.exists():
        return

    scores = [response.score for response in responses]
    avg = sum(scores) / len(scores)

    ProfileResult.objects.update_or_create(
        target=target,
        framework_name="Big Five",
        defaults={
            "score_data": {
                "Openness": avg,
                "Conscientiousness": avg,
                "Extraversion": avg,
                "Agreeableness": avg,
                "Neuroticism": avg,
            },
        },
    )
    logger.info("Calculated dummy Big Five results for %s", target.seed_username)
