import pytest

from core.models import Framework, Question, Target, Trait


@pytest.fixture
def target() -> Target:
    return Target.objects.create(seed_username="seed_user")


@pytest.fixture
def instrument() -> Framework:
    """A two-trait instrument with three items, one of them reverse scored."""
    framework = Framework.objects.create(
        slug="sample-instrument",
        name="Sample Instrument",
        citation="Test fixture, not a real instrument.",
        source_url="https://example.com/sample-instrument",
    )
    openness = Trait.objects.create(
        framework=framework,
        slug="openness",
        name="Openness",
    )
    caution = Trait.objects.create(framework=framework, slug="caution", name="Caution")
    Question.objects.create(
        framework=framework,
        trait=openness,
        question_id="Q1",
        text="Tries new things.",
    )
    Question.objects.create(
        framework=framework,
        trait=openness,
        question_id="Q2",
        text="Seeks out variety.",
    )
    Question.objects.create(
        framework=framework,
        trait=caution,
        question_id="Q3",
        text="Avoids taking risks.",
        reverse_scored=True,
    )
    return framework
