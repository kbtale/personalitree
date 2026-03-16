"""
Orchestrates the flow from truncated text to LLM evaluation and final scoring.
"""
import json
import logging
from core.models import Target, QuestionnaireResponse
from core.scraper.truncation import prepare_llm_payload
from core.llm.router import generate_llm_response
from core.scoring.engine import calculate_framework_scores

logger = logging.getLogger(__name__)

DEFAULT_PROMPT = "Evaluate this person's traits. Output ONLY a JSON array: [{\"id\": \"Q1\", \"score\": 3}]"

async def run_evaluation_pipeline(target_id: int):
    target = Target.objects.get(id=target_id)
    
    payload = prepare_llm_payload(target_id)
    if not payload:
        logger.warning("No payload for target %d", target_id)
        return

    try:
        response_text = await generate_llm_response(DEFAULT_PROMPT, payload)
        scores = json.loads(response_text)
        
        for item in scores:
            QuestionnaireResponse.objects.update_or_create(
                target=target,
                question_id=item["id"],
                defaults={"score": item["score"]}
            )
        
        calculate_framework_scores(target)
        
        target.status = Target.Status.COMPLETED
        target.save()
        logger.info("Evaluation pipeline complete for %s", target.seed_username)

    except Exception as exc:
        logger.error("Pipeline failed for %d: %s", target_id, exc)
        target.status = Target.Status.EVALUATING # Reset for retry or inspection
        target.save()
