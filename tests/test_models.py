from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone
import pytest

from core.models import (
    DiscoveredAccount,
    ProfileResult,
    QuestionnaireResponse,
    Target,
)

pytestmark = pytest.mark.django_db


def test_target_defaults_to_pending_status():
    target = Target.objects.create(seed_username="seed_user")

    assert target.status == Target.Status.PENDING


def test_target_str_contains_username_and_status():
    target = Target.objects.create(seed_username="seed_user")

    assert str(target) == "seed_user (pending)"


def test_targets_are_listed_newest_first():
    older = Target.objects.create(seed_username="first")
    newer = Target.objects.create(seed_username="second")
    Target.objects.filter(pk=older.pk).update(
        created_at=timezone.now() - timedelta(hours=1)
    )

    assert list(Target.objects.all()) == [newer, older]


def test_discovered_account_is_unique_per_target_platform_and_username():
    target = Target.objects.create(seed_username="seed_user")
    fields = {
        "target": target,
        "platform_name": "github",
        "url": "https://github.com/seed_user",
        "username": "seed_user",
    }
    DiscoveredAccount.objects.create(**fields)

    with pytest.raises(IntegrityError), transaction.atomic():
        DiscoveredAccount.objects.create(**fields)


def test_questionnaire_response_is_unique_per_target_and_question():
    target = Target.objects.create(seed_username="seed_user")
    fields = {"target": target, "question_id": "Q1", "score": 3}
    QuestionnaireResponse.objects.create(**fields)

    with pytest.raises(IntegrityError), transaction.atomic():
        QuestionnaireResponse.objects.create(**fields)


def test_profile_result_is_unique_per_target_and_framework():
    target = Target.objects.create(seed_username="seed_user")
    fields = {"target": target, "framework_name": "Big Five", "score_data": {}}
    ProfileResult.objects.create(**fields)

    with pytest.raises(IntegrityError), transaction.atomic():
        ProfileResult.objects.create(**fields)
