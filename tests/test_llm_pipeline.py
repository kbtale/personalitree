import asyncio
from unittest.mock import AsyncMock

import pytest

from core.exceptions import LLMProviderError, LLMResponseError, TargetNotFoundError
from core.llm import pipeline
from core.models import ProfileResult, QuestionnaireResponse, RawScrape, Target


@pytest.mark.django_db
def test_unknown_target_is_reported():
    with pytest.raises(TargetNotFoundError):
        asyncio.run(pipeline.run_evaluation_pipeline(999))


@pytest.mark.django_db(transaction=True)
def test_empty_payload_skips_the_evaluation(monkeypatch):
    target = Target.objects.create(
        seed_username="seed_user",
        status=Target.Status.SCRAPING,
    )
    generate = AsyncMock(return_value="[]")
    monkeypatch.setattr(pipeline, "generate_llm_response", generate)

    asyncio.run(pipeline.run_evaluation_pipeline(target.id))

    target.refresh_from_db()
    assert target.status == Target.Status.SCRAPING
    generate.assert_not_awaited()


@pytest.mark.django_db(transaction=True)
def test_scores_are_stored_and_the_target_completes(monkeypatch):
    target = Target.objects.create(seed_username="seed_user")
    RawScrape.objects.create(
        target=target,
        platform_name="github",
        raw_text_dump="profile text",
    )
    monkeypatch.setattr(
        pipeline,
        "generate_llm_response",
        AsyncMock(return_value='[{"id": "Q1", "score": 4}, {"id": "Q2", "score": 2}]'),
    )

    asyncio.run(pipeline.run_evaluation_pipeline(target.id))

    target.refresh_from_db()
    assert target.status == Target.Status.COMPLETED
    scores = dict(
        QuestionnaireResponse.objects.filter(target=target).values_list(
            "question_id", "score"
        )
    )
    assert scores == {"Q1": 4, "Q2": 2}
    profile = ProfileResult.objects.get(target=target)
    assert profile.score_data["Openness"] == 3.0


@pytest.mark.django_db(transaction=True)
def test_malformed_response_restores_the_evaluating_status(monkeypatch):
    target = Target.objects.create(seed_username="seed_user")
    RawScrape.objects.create(
        target=target,
        platform_name="github",
        raw_text_dump="profile text",
    )
    monkeypatch.setattr(
        pipeline,
        "generate_llm_response",
        AsyncMock(return_value="not json"),
    )

    asyncio.run(pipeline.run_evaluation_pipeline(target.id))

    target.refresh_from_db()
    assert target.status == Target.Status.EVALUATING
    assert not QuestionnaireResponse.objects.filter(target=target).exists()


@pytest.mark.django_db(transaction=True)
def test_provider_failure_restores_the_evaluating_status(monkeypatch):
    target = Target.objects.create(seed_username="seed_user")
    RawScrape.objects.create(
        target=target,
        platform_name="github",
        raw_text_dump="profile text",
    )
    monkeypatch.setattr(
        pipeline,
        "generate_llm_response",
        AsyncMock(side_effect=LLMProviderError("provider unavailable")),
    )

    asyncio.run(pipeline.run_evaluation_pipeline(target.id))

    target.refresh_from_db()
    assert target.status == Target.Status.EVALUATING


def test_valid_score_array_is_parsed():
    assert pipeline.parse_score_items('[{"id": "Q1", "score": 3}]') == [
        {"id": "Q1", "score": 3}
    ]


@pytest.mark.parametrize(
    "raw_response",
    [
        "not json",
        '{"id": "Q1", "score": 3}',
        "[3]",
        '[{"id": 1, "score": 3}]',
        '[{"id": "Q1", "score": "high"}]',
        '[{"id": "Q1"}]',
    ],
)
def test_invalid_score_payloads_are_rejected(raw_response):
    with pytest.raises(LLMResponseError):
        pipeline.parse_score_items(raw_response)
