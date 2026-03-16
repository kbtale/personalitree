"""
Shell for calculating personality framework scores from raw AI answers.
"""
import logging
from core.models import QuestionnaireResponse, ProfileResult

logger = logging.getLogger(__name__)

def calculate_framework_scores(target):
    _calculate_big_five(target)

def _calculate_big_five(target):
    responses = QuestionnaireResponse.objects.filter(target=target)
    if not responses.exists():
        return

    scores = [r.score for r in responses]
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
            }
        }
    )
    logger.info("Calculated dummy Big Five results for %s", target.seed_username)
