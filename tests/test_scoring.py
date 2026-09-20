import pytest

from core.constants import BIG_FIVE_TRAITS, Framework
from core.exceptions import QuestionnaireError
from core.models import ProfileResult, Question, QuestionnaireResponse, Target
from core.scoring.engine import calculate_framework_scores

pytestmark = pytest.mark.django_db

OPENNESS = BIG_FIVE_TRAITS[0]
CONSCIENTIOUSNESS = BIG_FIVE_TRAITS[1]
EXTRAVERSION = BIG_FIVE_TRAITS[2]


def _question(question_id: str, trait: str, reverse_scored: bool = False) -> Question:
    return Question.objects.create(
        question_id=question_id,
        framework_name=Framework.BIG_FIVE,
        trait=trait,
        text=f"item {question_id}",
        reverse_scored=reverse_scored,
    )


def _answer(target: Target, question: Question, score: int) -> None:
    QuestionnaireResponse.objects.create(target=target, question=question, score=score)


def test_no_responses_stores_null_for_every_trait(target):
    calculate_framework_scores(target)

    result = ProfileResult.objects.get(target=target)
    assert result.score_data == dict.fromkeys(BIG_FIVE_TRAITS, None)


def test_each_trait_averages_only_its_own_answers(target):
    _answer(target, _question("Q1", OPENNESS), 2)
    _answer(target, _question("Q2", OPENNESS), 4)
    _answer(target, _question("Q3", CONSCIENTIOUSNESS), 5)

    calculate_framework_scores(target)

    scores = ProfileResult.objects.get(target=target).score_data
    assert scores[OPENNESS] == 3.0
    assert scores[CONSCIENTIOUSNESS] == 5.0
    assert scores[EXTRAVERSION] is None


def test_reverse_scored_items_are_flipped(target):
    _answer(target, _question("Q1", OPENNESS, reverse_scored=True), 5)
    _answer(target, _question("Q2", OPENNESS), 1)

    calculate_framework_scores(target)

    assert ProfileResult.objects.get(target=target).score_data[OPENNESS] == 1.0


def test_second_run_updates_the_existing_row(target):
    _answer(target, _question("Q1", OPENNESS), 2)
    calculate_framework_scores(target)

    _answer(target, _question("Q2", OPENNESS), 4)
    calculate_framework_scores(target)

    assert ProfileResult.objects.filter(target=target).count() == 1
    assert ProfileResult.objects.get(target=target).score_data[OPENNESS] == 3.0


def test_unknown_framework_is_rejected(target):
    with pytest.raises(QuestionnaireError):
        calculate_framework_scores(target, "Enneagram")
