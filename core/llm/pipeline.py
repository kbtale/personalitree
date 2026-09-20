"""
Orchestrates the flow from truncated text to LLM evaluation and final scoring.
"""

import asyncio
import json
import logging
from typing import TypedDict

from core.constants import Framework
from core.exceptions import LLMError, LLMResponseError, QuestionnaireError
from core.llm.prompts import build_evaluation_prompt
from core.llm.router import generate_llm_response
from core.models import Question, QuestionnaireResponse, Target
from core.scoring.engine import calculate_framework_scores
from core.scraper.truncation import prepare_llm_payload

logger = logging.getLogger(__name__)


class ScoreItem(TypedDict):
    """A single questionnaire answer returned by the LLM."""

    id: str
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


def load_questions(framework_name: str = Framework.BIG_FIVE) -> list[Question]:
    """Return the ordered question bank for a framework, failing when empty."""
    questions = list(
        Question.objects.filter(framework_name=framework_name).order_by("question_id")
    )
    if not questions:
        raise QuestionnaireError(
            f"no questions loaded for {framework_name}; run load_questionnaire first"
        )
    return questions


async def run_evaluation_pipeline(target_id: int) -> None:
    target = await asyncio.to_thread(Target.objects.fetch, target_id)

    payload = await asyncio.to_thread(prepare_llm_payload, target_id)
    if not payload:
        logger.warning("No payload for target %d", target_id)
        return

    questions = await asyncio.to_thread(load_questions, Framework.BIG_FIVE)
    prompt = build_evaluation_prompt(questions)

    try:
        response_text = await generate_llm_response(prompt, payload)
        items = parse_score_items(response_text)
        await asyncio.to_thread(_store_scores, target, items)
        await asyncio.to_thread(calculate_framework_scores, target)
        await asyncio.to_thread(_mark_completed, target)
        logger.info("Evaluation pipeline complete for %s", target.seed_username)
    except LLMError:
        logger.exception("Evaluation failed for target %d", target_id)
        raise


def _store_scores(target: Target, items: list[ScoreItem]) -> None:
    for item in items:
        question = Question.objects.filter(
            framework_name=Framework.BIG_FIVE,
            question_id=item["id"],
        ).first()
        if question is None:
            raise LLMResponseError(f"unknown question id {item['id']}")
        QuestionnaireResponse.objects.update_or_create(
            target=target,
            question=question,
            defaults={"score": item["score"]},
        )


def _mark_completed(target: Target) -> None:
    target.status = Target.Status.COMPLETED
    target.save()
