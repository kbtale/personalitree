"""
Shell for calculating personality framework scores from raw AI answers.
"""

import logging

from django.db.models import Avg

from core.constants import BIG_FIVE_TRAITS, Framework
from core.models import ProfileResult, QuestionnaireResponse, Target

logger = logging.getLogger(__name__)


def calculate_framework_scores(target: Target) -> None:
    _calculate_big_five(target)


def _calculate_big_five(target: Target) -> None:
    average = QuestionnaireResponse.objects.filter(target=target).aggregate(
        average_score=Avg("score")
    )["average_score"]
    if average is None:
        return

    ProfileResult.objects.update_or_create(
        target=target,
        framework_name=Framework.BIG_FIVE,
        defaults={"score_data": dict.fromkeys(BIG_FIVE_TRAITS, average)},
    )
    logger.info("Calculated dummy Big Five results for %s", target.seed_username)
