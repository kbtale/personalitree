import asyncio
from unittest.mock import AsyncMock

import pytest

from core.constants import BIG_FIVE_TRAITS, Framework
from core.exceptions import (
    LLMProviderError,
    LLMResponseError,
    QuestionnaireError,
    TargetNotFoundError,
)
from core.llm import pipeline
from core.models import (
    ProfileResult,
    Question,
    QuestionnaireResponse,
    RawScrape,
    Target,
)


def _add_question(question_id: str) -> Question:
    return Question.objects.create(
        question_id=question_id,
        framework_name=Framework.BIG_FIVE,
        trait=BIG_FIVE_TRAITS[0],
        text="I enjoy trying new things.",
    )


def _add_scrape(target: Target) -> RawScrape:
    return RawScrape.objects.create(
        target=target,
        platform_name="github",
        raw_text_dump="profile text",
    )


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
def test_missing_question_bank_is_reported():
    target = Target.objects.create(seed_username="seed_user")
    _add_scrape(target)

    with pytest.raises(QuestionnaireError):
        asyncio.run(pipeline.run_evaluation_pipeline(target.id))


@pytest.mark.django_db(transaction=True)
def test_scores_are_stored_and_the_target_completes(monkeypatch):
    target = Target.objects.create(seed_username="seed_user")
    _add_scrape(target)
    _add_question("Q1")
    _add_question("Q2")
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
            "question__question_id", "score"
        )
    )
    assert scores == {"Q1": 4, "Q2": 2}
    profile = ProfileResult.objects.get(target=target)
    assert profile.score_data["Openness"] == 3.0


@pytest.mark.django_db(transaction=True)
def test_malformed_response_is_raised_to_the_caller(monkeypatch):
    target = Target.objects.create(seed_username="seed_user")
    _add_scrape(target)
    _add_question("Q1")
    monkeypatch.setattr(
        pipeline,
        "generate_llm_response",
        AsyncMock(return_value="not json"),
    )

    with pytest.raises(LLMResponseError):
        asyncio.run(pipeline.run_evaluation_pipeline(target.id))

    assert not QuestionnaireResponse.objects.filter(target=target).exists()


@pytest.mark.django_db(transaction=True)
def test_provider_failure_is_raised_to_the_caller(monkeypatch):
    target = Target.objects.create(seed_username="seed_user")
    _add_scrape(target)
    _add_question("Q1")
    monkeypatch.setattr(
        pipeline,
        "generate_llm_response",
        AsyncMock(side_effect=LLMProviderError("provider unavailable")),
    )

    with pytest.raises(LLMProviderError):
        asyncio.run(pipeline.run_evaluation_pipeline(target.id))


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


@pytest.mark.django_db
def test_validate_score_items_matches_questions():
    question = _add_question("Q1")

    answers = pipeline.validate_score_items([{"id": "Q1", "score": 4}], [question])

    assert answers == [{"question": question, "score": 4}]


@pytest.mark.django_db
def test_validate_score_items_rejects_unknown_ids():
    question = _add_question("Q1")

    with pytest.raises(LLMResponseError):
        pipeline.validate_score_items([{"id": "Q9", "score": 3}], [question])


@pytest.mark.django_db
def test_validate_score_items_rejects_out_of_range_scores():
    question = _add_question("Q1")

    with pytest.raises(LLMResponseError):
        pipeline.validate_score_items([{"id": "Q1", "score": 9}], [question])


@pytest.mark.django_db
def test_validate_score_items_rejects_duplicate_answers():
    question = _add_question("Q1")

    with pytest.raises(LLMResponseError):
        pipeline.validate_score_items(
            [{"id": "Q1", "score": 3}, {"id": "Q1", "score": 4}],
            [question],
        )


@pytest.mark.django_db
def test_validate_score_items_rejects_missing_answers():
    q1 = _add_question("Q1")
    q2 = _add_question("Q2")

    with pytest.raises(LLMResponseError):
        pipeline.validate_score_items([{"id": "Q1", "score": 3}], [q1, q2])
