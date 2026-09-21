from io import StringIO
from pathlib import Path

from django.core.management import call_command
import pytest

from core.models import Framework

pytestmark = pytest.mark.django_db

BANK = Path(__file__).resolve().parent.parent / "banks" / "mini-ipip6-24.json"

DIRECT_AND_REVERSED = {
    "extraversion": (2, 2),
    "agreeableness": (2, 2),
    "conscientiousness": (2, 2),
    "neuroticism": (2, 2),
    "openness": (1, 3),
    "honesty-humility": (0, 4),
}


def _load() -> Framework:
    call_command("load_questionnaire", BANK, stdout=StringIO())
    return Framework.objects.get(slug="mini-ipip6-24")


def test_the_shipped_bank_loads_twenty_four_items_across_six_traits():
    framework = _load()

    assert framework.traits.count() == 6
    assert framework.questions.count() == 24


def test_the_shipped_bank_carries_its_provenance():
    framework = _load()

    assert framework.citation.startswith("Milojev")
    assert "ipip.ori.org" in framework.citation
    assert framework.source_url == "https://ipip.ori.org/MiniIPIP6Key.htm"


def test_every_trait_keeps_the_keying_the_source_publishes():
    framework = _load()

    direct_total = 0
    reversed_total = 0
    for slug, (direct, reversed_items) in DIRECT_AND_REVERSED.items():
        questions = framework.questions.filter(trait__slug=slug)
        assert questions.count() == 4
        assert questions.filter(reverse_scored=False).count() == direct
        assert questions.filter(reverse_scored=True).count() == reversed_items
        direct_total += direct
        reversed_total += reversed_items

    assert direct_total == 9
    assert reversed_total == 15


def test_every_item_is_a_third_person_statement():
    framework = _load()

    for question in framework.questions.all():
        assert question.text
        assert not question.text.startswith("I ")
