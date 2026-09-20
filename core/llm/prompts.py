"""Prompts sent to the configured LLM provider."""

from collections.abc import Sequence

from core.models import Framework, Question

INSTRUCTION = (
    "Evaluate the person described by the profile text. Score every item on the "
    "scale given with it and answer with ONLY a JSON array of objects shaped "
    'like {"id": "<item id>", "score": <integer>}.'
)


def build_evaluation_prompt(
    framework: Framework,
    questions: Sequence[Question],
) -> str:
    """Render one instrument into an evaluation prompt."""
    items = [
        f"- {question.question_id} ({question.min_score}-{question.max_score}): "
        f"{question.text}"
        for question in questions
    ]
    return "\n".join(
        [INSTRUCTION, "", f"Instrument: {framework.name}", "Items:", *items]
    )
