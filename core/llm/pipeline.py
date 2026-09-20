"""
Orchestrates the flow from truncated text to LLM evaluation and final scoring.
"""

import asyncio
from collections.abc import Sequence
import json
import logging
from typing import TypedDict

from core.exceptions import LLMError, LLMResponseError, QuestionnaireError
from core.llm.prompts import build_evaluation_prompt
from core.llm.router import generate_llm_response
from core.models import Framework, Question, QuestionnaireResponse, Target
from core.scoring.engine import calculate_framework_scores
from core.scraper.truncation import prepare_llm_payload

logger = logging.getLogger(__name__)


class ScoreItem(TypedDict):
    """A single questionnaire answer returned by the LLM."""

    id: str
    score: int


class Answer(TypedDict):
    """An answer matched to a stored question and ready to persist."""

    question: Question
    score: int


def parse_score_items(raw_response: str) -> list[ScoreItem]:
    """Parse the JSON array returned by the LLM into validated score items."""
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise LLMResponseError("response is not valid JSON") from exc

    if not isinstance(payload, list):
        raise LLMResponseError("response is not a JSON array")

    items: list[ScoreItem] = []
    for entry in payload:
        if not isinstance(entry, dict):
            raise LLMResponseError("score entry is not an object")
        question_id = entry.get("id")
        score = entry.get("score")
        if not isinstance(question_id, str) or not isinstance(score, int):
            raise LLMResponseError("score entry needs a string id and integer score")
        items.append({"id": question_id, "score": score})
    return items


def validate_score_items(
    items: list[ScoreItem],
    questions: Sequence[Question],
) -> list[Answer]:
    """Match score items to the bank, rejecting unknown or incomplete answers."""
    bank = {question.question_id: question for question in questions}
    answers: list[Answer] = []
    answered: set[str] = set()

    for item in items:
        question_id = item["id"]
        if question_id in answered:
            raise LLMResponseError(f"duplicate answer for {question_id}")
        question = bank.get(question_id)
        if question is None:
            raise LLMResponseError(f"unknown question id {question_id}")
        if not question.min_score <= item["score"] <= question.max_score:
            raise LLMResponseError(
                f"score for {question_id} is outside {question.min_score}"
                f"-{question.max_score}"
            )
        answered.add(question_id)
        answers.append({"question": question, "score": item["score"]})

    missing = sorted(set(bank) - answered)
    if missing:
        raise LLMResponseError(f"missing answers for {', '.join(missing)}")
    return answers


def load_frameworks() -> list[Framework]:
    """Return the active instruments, failing when nothing is loaded."""
    frameworks = list(Framework.objects.filter(is_active=True).order_by("slug"))
    if not frameworks:
        raise QuestionnaireError("no active instrument; run load_questionnaire first")
    return frameworks


def load_questions(framework: Framework) -> list[Question]:
    """Return the ordered items of one instrument, failing when it has none."""
    questions = list(framework.questions.order_by("question_id"))
    if not questions:
        raise QuestionnaireError(f"{framework.slug} has no items loaded")
    return questions


async def run_evaluation_pipeline(target_id: int) -> None:
    target = await asyncio.to_thread(Target.objects.fetch, target_id)

    payload = await asyncio.to_thread(prepare_llm_payload, target_id)
    if not payload:
        logger.warning("No payload for target %d", target_id)
        return

    frameworks = await asyncio.to_thread(load_frameworks)

    try:
        for framework in frameworks:
            await evaluate_framework(target, framework, payload)
        await asyncio.to_thread(_mark_completed, target)
        logger.info("Evaluation pipeline complete for %s", target.seed_username)
    except LLMError:
        logger.exception("Evaluation failed for target %d", target_id)
        raise


async def evaluate_framework(
    target: Target,
    framework: Framework,
    payload: str,
) -> None:
    """Ask the provider about one instrument, then store its answers and scores."""
    questions = await asyncio.to_thread(load_questions, framework)
    prompt = build_evaluation_prompt(framework, questions)

    try:
        response_text = await generate_llm_response(prompt, payload)
        items = parse_score_items(response_text)
        answers = validate_score_items(items, questions)
    except LLMError as exc:
        raise _named(exc, framework) from exc

    await asyncio.to_thread(_store_scores, target, answers)
    await asyncio.to_thread(calculate_framework_scores, target, framework)


def _named(error: LLMError, framework: Framework) -> LLMError:
    """Prefix an error with the instrument it came from."""
    return type(error)(f"{framework.slug}: {error}")


def _store_scores(target: Target, answers: list[Answer]) -> None:
    for answer in answers:
        QuestionnaireResponse.objects.update_or_create(
            target=target,
            question=answer["question"],
            defaults={"score": answer["score"]},
        )


def _mark_completed(target: Target) -> None:
    target.status = Target.Status.COMPLETED
    target.save()
