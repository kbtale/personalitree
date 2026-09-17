import pytest

from core.constants import BIG_FIVE_TRAITS, FRAMEWORK_BIG_FIVE
from core.models import ProfileResult, QuestionnaireResponse, Target
from core.scoring.engine import calculate_framework_scores

pytestmark = pytest.mark.django_db


def _add_responses(target: Target, scores: list[int], start: int = 0) -> None:
    for offset, score in enumerate(scores):
        QuestionnaireResponse.objects.create(
            target=target,
            question_id=f"Q{start + offset}",
            score=score,
        )


def test_no_responses_creates_no_profile_result(target):
    calculate_framework_scores(target)

    assert not ProfileResult.objects.filter(target=target).exists()


def test_average_is_written_for_every_trait(target):
    _add_responses(target, [2, 4])

    calculate_framework_scores(target)

    result = ProfileResult.objects.get(target=target)
    assert result.framework_name == FRAMEWORK_BIG_FIVE
    assert result.score_data == dict.fromkeys(BIG_FIVE_TRAITS, 3.0)


def test_second_run_updates_the_existing_row(target):
    _add_responses(target, [2, 4])
    calculate_framework_scores(target)

    _add_responses(target, [5], start=2)
    calculate_framework_scores(target)

    assert ProfileResult.objects.filter(target=target).count() == 1
    assert ProfileResult.objects.get(target=target).score_data["Openness"] == 11 / 3
