from io import StringIO
from pathlib import Path

from django.core.management import call_command
import pytest

from core.models import Framework, ProfileResult, QuestionnaireResponse, Target
from core.scoring.engine import calculate_framework_scores

pytestmark = pytest.mark.django_db

BANK = Path(__file__).resolve().parent.parent / "banks" / "oejts-1.2.json"

PUBLISHED_KEY = {
    "ie": {
        "positive": ("Q15", "Q23", "Q27"),
        "negative": ("Q3", "Q7", "Q11", "Q19", "Q31"),
        "constant": 30,
    },
    "sn": {
        "positive": ("Q4", "Q8", "Q12", "Q16", "Q20", "Q32"),
        "negative": ("Q24", "Q28"),
        "constant": 12,
    },
    "ft": {
        "positive": ("Q6", "Q10", "Q22"),
        "negative": ("Q2", "Q14", "Q18", "Q26", "Q30"),
        "constant": 30,
    },
    "jp": {
        "positive": ("Q1", "Q5", "Q13", "Q21", "Q29"),
        "negative": ("Q9", "Q17", "Q25"),
        "constant": 18,
    },
}
ITEMS_PER_TRAIT = 8
CUT = 24


def _load() -> Framework:
    call_command("load_questionnaire", BANK, stdout=StringIO())
    return Framework.objects.get(slug="oejts-1.2")


def _answer(framework: Framework, target: Target, value) -> None:
    for question in framework.questions.all():
        QuestionnaireResponse.objects.create(
            target=target,
            question=question,
            score=value(question.question_id),
        )


def _published_sum(slug: str, value) -> int:
    key = PUBLISHED_KEY[slug]
    return (
        key["constant"]
        + sum(value(item_id) for item_id in key["positive"])
        - sum(value(item_id) for item_id in key["negative"])
    )


def _varying_value(item_id: str) -> int:
    return 1 + int(item_id[1:]) % 5


def test_the_shipped_bank_loads_thirty_two_items_across_four_dichotomies():
    framework = _load()

    assert framework.traits.count() == 4
    assert framework.questions.count() == 32
    assert framework.is_active is True


def test_the_shipped_bank_carries_its_provenance():
    framework = _load()

    assert framework.citation.startswith("Jorgenson")
    assert framework.source_url.endswith("OEJTS1.2.pdf")


def test_every_dichotomy_keeps_the_keying_the_source_publishes():
    framework = _load()

    for slug, key in PUBLISHED_KEY.items():
        questions = framework.questions.filter(trait__slug=slug)
        assert questions.count() == ITEMS_PER_TRAIT
        assert set(questions.values_list("question_id", flat=True)) == set(
            key["positive"] + key["negative"]
        )
        assert set(
            questions.filter(reverse_scored=True).values_list("question_id", flat=True)
        ) == set(key["negative"])


def test_the_average_equals_the_published_sum_over_eight():
    framework = _load()
    target = Target.objects.create(seed_username="oejts-verification")
    _answer(framework, target, _varying_value)

    calculate_framework_scores(target, framework)
    result = ProfileResult.objects.get(target=target, framework=framework)

    for slug in PUBLISHED_KEY:
        average = result.score_data[slug]["average"]
        assert average * ITEMS_PER_TRAIT == _published_sum(slug, _varying_value)
        assert result.score_data[slug]["answers"] == ITEMS_PER_TRAIT


def test_the_published_cut_is_an_average_of_three():
    framework = _load()
    target = Target.objects.create(seed_username="oejts-midpoint")
    _answer(framework, target, lambda item_id: 3)

    calculate_framework_scores(target, framework)
    result = ProfileResult.objects.get(target=target, framework=framework)

    for slug in PUBLISHED_KEY:
        assert result.score_data[slug]["average"] == 3.0
        assert _published_sum(slug, lambda item_id: 3) == CUT


def test_the_shipped_bank_declares_its_letters_in_type_order():
    framework = _load()

    traits = list(framework.traits.all())

    assert [trait.slug for trait in traits] == ["ie", "sn", "ft", "jp"]
    assert [trait.position for trait in traits] == [1, 2, 3, 4]
    assert [(trait.high_label, trait.low_label) for trait in traits] == [
        ("E", "I"),
        ("N", "S"),
        ("T", "F"),
        ("P", "J"),
    ]
