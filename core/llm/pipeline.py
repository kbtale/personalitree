"""
Orchestrates the flow from truncated text to LLM evaluation and final scoring.
"""

import asyncio
import json
import logging
from typing import TypedDict

from core.exceptions import LLMError, LLMResponseError
from core.llm.prompts import TRAIT_EVALUATION_PROMPT
from core.llm.router import generate_llm_response
from core.models import QuestionnaireResponse, Target
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


async def run_evaluation_pipeline(target_id: int) -> None:
    target = await asyncio.to_thread(Target.objects.fetch, target_id)

    payload = await asyncio.to_thread(prepare_llm_payload, target_id)
    if not payload:
        logger.warning("No payload for target %d", target_id)
        return

    try:
        response_text = await generate_llm_response(TRAIT_EVALUATION_PROMPT, payload)
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
        QuestionnaireResponse.objects.update_or_create(
            target=target,
            question_id=item["id"],
            defaults={"score": item["score"]},
        )


def _mark_completed(target: Target) -> None:
    target.status = Target.Status.COMPLETED
    target.save()
