import asyncio
from unittest.mock import AsyncMock

import pytest

from core.exceptions import (
    LLMProviderError,
    LLMResponseError,
    QuestionnaireError,
    TargetNotFoundError,
)
from core.llm import pipeline
from core.models import (
    Framework,
    ProfileResult,
    Question,
    QuestionnaireResponse,
    RawScrape,
    Target,
    Trait,
)


def _add_scrape(target: Target) -> RawScrape:
    return RawScrape.objects.create(
        target=target,
        platform_name="github",
        raw_text_dump="profile text",
    )


def _other_instrument() -> Framework:
    """A second instrument, one trait and one item, to prove both are evaluated."""
    framework = Framework.objects.create(
        slug="other-instrument",
        name="Other Instrument",
    )
    trait = Trait.objects.create(
        framework=framework, slug="curiosity", name="Curiosity"
    )
    Question.objects.create(
        framework=framework,
        trait=trait,
        question_id="A1",
        text="Asks a lot of questions.",
    )
    return framework


def _respond(prompt: str, responses: dict[str, str]) -> str:
    for instrument_name, body in responses.items():
        if instrument_name in prompt:
            return body
    raise AssertionError(f"no stubbed response for: {prompt[:80]}")


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
def test_missing_instrument_is_reported(target):
    _add_scrape(target)

    with pytest.raises(QuestionnaireError):
        asyncio.run(pipeline.run_evaluation_pipeline(target.id))


@pytest.mark.django_db(transaction=True)
def test_inactive_instruments_are_not_evaluated(instrument, target):
    instrument.is_active = False
    instrument.save(update_fields=["is_active"])
    _add_scrape(target)

    with pytest.raises(QuestionnaireError):
        asyncio.run(pipeline.run_evaluation_pipeline(target.id))


@pytest.mark.django_db(transaction=True)
def test_instrument_without_items_is_reported(instrument, monkeypatch, target):
    instrument.questions.all().delete()
    _add_scrape(target)
    monkeypatch.setattr(
        pipeline,
        "generate_llm_response",
        AsyncMock(return_value="[]"),
    )

    with pytest.raises(QuestionnaireError) as error:
        asyncio.run(pipeline.run_evaluation_pipeline(target.id))

    assert instrument.slug in str(error.value)


@pytest.mark.django_db(transaction=True)
def test_every_active_instrument_is_evaluated(instrument, monkeypatch, target):
    _add_scrape(target)
    _other_instrument()
    responses = {
        "Sample Instrument": (
            '[{"id": "Q1", "score": 5}, {"id": "Q2", "score": 3},'
            ' {"id": "Q3", "score": 2}]'
        ),
        "Other Instrument": '[{"id": "A1", "score": 4}]',
    }
    monkeypatch.setattr(
        pipeline,
        "generate_llm_response",
        AsyncMock(side_effect=lambda prompt, payload: _respond(prompt, responses)),
    )

    asyncio.run(pipeline.run_evaluation_pipeline(target.id))

    target.refresh_from_db()
    assert target.status == Target.Status.COMPLETED
    assert QuestionnaireResponse.objects.filter(target=target).count() == 4

    sample = ProfileResult.objects.get(target=target, framework=instrument)
    assert sample.score_data["openness"]["average"] == 4.0
    assert sample.score_data["caution"]["average"] == 4.0

    other = ProfileResult.objects.get(target=target, framework__slug="other-instrument")
    assert other.score_data["curiosity"]["average"] == 4.0


@pytest.mark.django_db(transaction=True)
def test_malformed_response_names_the_instrument(instrument, monkeypatch, target):
    _add_scrape(target)
    monkeypatch.setattr(
        pipeline,
        "generate_llm_response",
        AsyncMock(return_value="not json"),
    )

    with pytest.raises(LLMResponseError) as error:
        asyncio.run(pipeline.run_evaluation_pipeline(target.id))

    assert instrument.slug in str(error.value)
    assert not QuestionnaireResponse.objects.filter(target=target).exists()


@pytest.mark.django_db(transaction=True)
def test_provider_failure_names_the_instrument(instrument, monkeypatch, target):
    _add_scrape(target)
    monkeypatch.setattr(
        pipeline,
        "generate_llm_response",
        AsyncMock(side_effect=LLMProviderError("provider unavailable")),
    )

    with pytest.raises(LLMProviderError) as error:
        asyncio.run(pipeline.run_evaluation_pipeline(target.id))

    assert instrument.slug in str(error.value)


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
def test_validate_score_items_matches_questions(instrument):
    question = instrument.questions.get(question_id="Q1")

    answers = pipeline.validate_score_items([{"id": "Q1", "score": 4}], [question])

    assert answers == [{"question": question, "score": 4}]


@pytest.mark.django_db
def test_validate_score_items_rejects_unknown_ids(instrument):
    question = instrument.questions.get(question_id="Q1")

    with pytest.raises(LLMResponseError):
        pipeline.validate_score_items([{"id": "Q9", "score": 3}], [question])


@pytest.mark.django_db
def test_validate_score_items_rejects_out_of_range_scores(instrument):
    question = instrument.questions.get(question_id="Q1")

    with pytest.raises(LLMResponseError):
        pipeline.validate_score_items([{"id": "Q1", "score": 9}], [question])


@pytest.mark.django_db
def test_validate_score_items_rejects_duplicate_answers(instrument):
    question = instrument.questions.get(question_id="Q1")

    with pytest.raises(LLMResponseError):
        pipeline.validate_score_items(
            [{"id": "Q1", "score": 3}, {"id": "Q1", "score": 4}],
            [question],
        )


@pytest.mark.django_db
def test_validate_score_items_rejects_missing_answers(instrument):
    questions = list(instrument.questions.order_by("question_id"))

    with pytest.raises(LLMResponseError):
        pipeline.validate_score_items([{"id": "Q1", "score": 3}], questions)
