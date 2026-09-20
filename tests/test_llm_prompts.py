from core.constants import BIG_FIVE_TRAITS, Framework
from core.llm.prompts import build_evaluation_prompt
from core.models import Question


def _question(question_id: str, **overrides) -> Question:
    fields = {
        "question_id": question_id,
        "framework_name": Framework.BIG_FIVE,
        "trait": BIG_FIVE_TRAITS[0],
        "text": f"item {question_id}",
    }
    fields.update(overrides)
    return Question(**fields)


def test_prompt_lists_every_item_with_its_scale():
    prompt = build_evaluation_prompt(
        [
            _question("Q1"),
            _question("Q2", min_score=1, max_score=7),
        ]
    )

    assert "Q1 (1-5): item Q1" in prompt
    assert "Q2 (1-7): item Q2" in prompt
    assert "JSON array" in prompt


def test_prompt_is_rendered_for_an_empty_bank():
    prompt = build_evaluation_prompt([])

    assert "Items:" in prompt
    assert "Q1" not in prompt
