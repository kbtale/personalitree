from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone
import pytest

from core.models import (
    DiscoveredAccount,
    Framework,
    ProfileResult,
    Question,
    QuestionnaireResponse,
    RawScrape,
    Target,
    Trait,
)

pytestmark = pytest.mark.django_db


def test_target_defaults_to_pending_status():
    target = Target.objects.create(seed_username="seed_user")

    assert target.status == Target.Status.PENDING


def test_target_str_contains_username_and_status():
    target = Target.objects.create(seed_username="seed_user")

    assert str(target) == "seed_user (pending)"


def test_new_target_has_no_attempts_and_no_error():
    target = Target.objects.create(seed_username="seed_user")

    assert target.attempts == 0
    assert target.last_error == ""


def test_targets_are_listed_newest_first():
    older = Target.objects.create(seed_username="first")
    newer = Target.objects.create(seed_username="second")
    Target.objects.filter(pk=older.pk).update(
        created_at=timezone.now() - timedelta(hours=1)
    )

    assert list(Target.objects.all()) == [newer, older]


def test_discovered_account_is_unique_per_target_platform_and_username(target):
    fields = {
        "target": target,
        "platform_name": "github",
        "url": "https://github.com/seed_user",
        "username": "seed_user",
    }
    DiscoveredAccount.objects.create(**fields)

    with pytest.raises(IntegrityError), transaction.atomic():
        DiscoveredAccount.objects.create(**fields)


def test_raw_scrape_is_unique_per_target_and_platform(target):
    fields = {"target": target, "platform_name": "github", "raw_text_dump": "text"}
    RawScrape.objects.create(**fields)

    with pytest.raises(IntegrityError), transaction.atomic():
        RawScrape.objects.create(**fields)


def test_framework_slug_is_unique(instrument):
    with pytest.raises(IntegrityError), transaction.atomic():
        Framework.objects.create(slug=instrument.slug, name="Another instrument")


def test_trait_slug_is_unique_per_framework(instrument):
    with pytest.raises(IntegrityError), transaction.atomic():
        Trait.objects.create(
            framework=instrument,
            slug="openness",
            name="Openness again",
        )


def test_question_id_is_unique_per_framework(instrument):
    with pytest.raises(IntegrityError), transaction.atomic():
        Question.objects.create(
            framework=instrument,
            trait=instrument.traits.first(),
            question_id="Q1",
            text="A second Q1.",
        )


def test_question_rejects_a_trait_from_another_framework(instrument):
    other = Framework.objects.create(slug="other-instrument", name="Other")
    foreign = Trait.objects.create(framework=other, slug="foreign", name="Foreign")
    question = Question(
        framework=instrument,
        trait=foreign,
        question_id="Q9",
        text="Belongs to no item of this instrument.",
    )

    with pytest.raises(ValidationError):
        question.full_clean()


def test_question_rejects_an_inverted_scale(instrument):
    question = Question(
        framework=instrument,
        trait=instrument.traits.first(),
        question_id="Q9",
        text="Impossible scale.",
        min_score=4,
        max_score=2,
    )

    with pytest.raises(ValidationError):
        question.full_clean()


def test_questionnaire_response_is_unique_per_target_and_question(instrument, target):
    fields = {
        "target": target,
        "question": instrument.questions.get(question_id="Q1"),
        "score": 3,
    }
    QuestionnaireResponse.objects.create(**fields)

    with pytest.raises(IntegrityError), transaction.atomic():
        QuestionnaireResponse.objects.create(**fields)


def test_profile_result_is_unique_per_target_and_framework(instrument, target):
    fields = {"target": target, "framework": instrument, "score_data": {}}
    ProfileResult.objects.create(**fields)

    with pytest.raises(IntegrityError), transaction.atomic():
        ProfileResult.objects.create(**fields)
