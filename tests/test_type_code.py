from io import StringIO
from pathlib import Path
from typing import Any

from django.core.management import call_command
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
from core.scoring.type_code import letter, scale_midpoint, type_code

pytestmark = pytest.mark.django_db

BANK = Path(__file__).resolve().parent.parent / "banks" / "oejts-1.2.json"


def _load() -> Framework:
    call_command("load_questionnaire", BANK, stdout=StringIO())
    return Framework.objects.get(slug="oejts-1.2")


def _scores(**averages: float | None) -> dict[str, Any]:
    return {
        slug: {"name": slug, "average": average, "answers": 8}
        for slug, average in averages.items()
    }


def _answer(framework: Framework, target: Target, score) -> None:
    for question in framework.questions.all():
        QuestionnaireResponse.objects.create(
            target=target,
            question=question,
            score=score(question),
        )


def test_the_midpoint_comes_from_the_items_the_instrument_declares():
    framework = _load()

    assert scale_midpoint(framework) == 3.0


def test_a_wider_scale_moves_the_midpoint_with_it():
    framework = Framework.objects.create(slug="wider", name="Wider")
    trait = Trait.objects.create(framework=framework, slug="only", name="Only")
    Question.objects.create(
        framework=framework,
        trait=trait,
        question_id="Q1",
        text="Something.",
        min_score=1,
        max_score=7,
    )

    assert scale_midpoint(framework) == 4.0


def test_averages_above_the_midpoint_read_the_high_side():
    framework = _load()
    traits = {trait.slug: trait for trait in framework.traits.all()}

    code = type_code(framework, _scores(ie=4.0, sn=3.5, ft=3.25, jp=5.0))

    assert code == "ENTP"
    assert letter(traits["ie"], 4.0, 3.0) == "E"
    assert letter(traits["jp"], 2.0, 3.0) == "J"


def test_the_cut_reads_the_low_side_at_exactly_the_midpoint():
    framework = _load()

    assert type_code(framework, _scores(ie=3.0, sn=3.0, ft=3.0, jp=3.0)) == "ISFJ"


def test_a_trait_with_no_answers_withholds_the_type():
    framework = _load()

    assert type_code(framework, _scores(ie=4.0, sn=4.0, ft=None, jp=4.0)) is None


def test_an_instrument_without_labels_has_no_type(instrument):
    assert type_code(instrument, {"openness": {"average": 4.0}}) is None
    assert instrument.traits.first().high_label == ""


def test_the_type_follows_the_items_that_were_answered():
    framework = _load()
    target = Target.objects.create(seed_username="oejts-typed")
    _answer(framework, target, lambda question: 1 if question.reverse_scored else 5)

    calculate_framework_scores(target, framework)

    result = ProfileResult.objects.get(target=target, framework=framework)
    assert type_code(framework, result.score_data) == "ENTP"


def test_answering_against_the_key_reads_the_other_poles():
    framework = _load()
    target = Target.objects.create(seed_username="oejts-against")
    _answer(framework, target, lambda question: 5 if question.reverse_scored else 1)

    calculate_framework_scores(target, framework)

    result = ProfileResult.objects.get(target=target, framework=framework)
    assert type_code(framework, result.score_data) == "ISFJ"
