import pytest

from core.models import (
    Framework,
    ProfileResult,
    Question,
    QuestionnaireResponse,
    Target,
    Trait,
)
from core.scoring.engine import calculate_framework_scores

pytestmark = pytest.mark.django_db


def _answer(target: Target, question: Question, score: int) -> None:
    QuestionnaireResponse.objects.create(target=target, question=question, score=score)


def _questions(instrument: Framework) -> dict[str, Question]:
    return {question.question_id: question for question in instrument.questions.all()}


def test_each_trait_scores_only_its_own_items(instrument, target):
    questions = _questions(instrument)
    _answer(target, questions["Q1"], 2)
    _answer(target, questions["Q2"], 4)
    _answer(target, questions["Q3"], 5)

    calculate_framework_scores(target, instrument)

    scores = ProfileResult.objects.get(target=target, framework=instrument).score_data
    assert scores["openness"]["average"] == 3.0
    assert scores["openness"]["answers"] == 2
    assert scores["caution"]["average"] == 1.0
    assert scores["caution"]["answers"] == 1


def test_unanswered_trait_scores_null_rather_than_zero(instrument, target):
    calculate_framework_scores(target, instrument)

    scores = ProfileResult.objects.get(target=target, framework=instrument).score_data
    assert scores["openness"] == {"name": "Openness", "average": None, "answers": 0}


def test_second_run_updates_the_existing_row(instrument, target):
    questions = _questions(instrument)
    _answer(target, questions["Q1"], 2)
    calculate_framework_scores(target, instrument)

    _answer(target, questions["Q2"], 4)
    calculate_framework_scores(target, instrument)

    rows = ProfileResult.objects.filter(target=target, framework=instrument)
    assert rows.count() == 1
    assert rows.first().score_data["openness"]["average"] == 3.0


def test_answers_from_another_instrument_are_ignored(instrument, target):
    other = Framework.objects.create(slug="other-instrument", name="Other")
    foreign_trait = Trait.objects.create(
        framework=other,
        slug="foreign",
        name="Foreign",
    )
    foreign_question = Question.objects.create(
        framework=other,
        trait=foreign_trait,
        question_id="Q1",
        text="Foreign item.",
    )
    _answer(target, foreign_question, 5)
    _answer(target, _questions(instrument)["Q1"], 1)

    calculate_framework_scores(target, instrument)

    scores = ProfileResult.objects.get(target=target, framework=instrument).score_data
    assert scores["openness"]["average"] == 1.0
