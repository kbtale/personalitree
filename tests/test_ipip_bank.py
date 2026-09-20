from io import StringIO
from pathlib import Path

from django.core.management import call_command
import pytest

from core.models import Framework

pytestmark = pytest.mark.django_db

BANK = Path(__file__).resolve().parent.parent / "banks" / "ipip-big-five-50.json"

DIRECT_AND_REVERSED = {
    "extraversion": (5, 5),
    "agreeableness": (6, 4),
    "conscientiousness": (6, 4),
    "emotional-stability": (2, 8),
    "intellect-imagination": (7, 3),
}


def _load() -> Framework:
    call_command("load_questionnaire", BANK, stdout=StringIO())
    return Framework.objects.get(slug="ipip-big-five-50")


def test_the_shipped_bank_loads_fifty_items_across_five_traits():
    framework = _load()

    assert framework.traits.count() == 5
    assert framework.questions.count() == 50
    assert framework.is_active is True


def test_the_shipped_bank_carries_its_provenance():
    framework = _load()

    assert framework.citation.startswith("Goldberg")
    assert "public domain" in framework.citation
    assert framework.source_url == "https://ipip.ori.org/New_IPIP-50-item-scale.htm"


def test_every_trait_keeps_the_keying_the_source_publishes():
    framework = _load()

    for slug, (direct, reversed_items) in DIRECT_AND_REVERSED.items():
        questions = framework.questions.filter(trait__slug=slug)
        assert questions.count() == 10
        assert questions.filter(reverse_scored=False).count() == direct
        assert questions.filter(reverse_scored=True).count() == reversed_items


def test_every_item_is_a_third_person_statement_with_a_scale():
    framework = _load()

    for question in framework.questions.all():
        assert question.text
        assert not question.text.startswith("I ")
        assert (question.min_score, question.max_score) == (1, 5)
