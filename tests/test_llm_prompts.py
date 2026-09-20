import pytest

from core.llm.prompts import build_evaluation_prompt

pytestmark = pytest.mark.django_db


def test_prompt_names_the_instrument_and_every_item_with_its_scale(instrument):
    question = instrument.questions.get(question_id="Q1")
    question.max_score = 7

    prompt = build_evaluation_prompt(instrument, [question])

    assert "Instrument: Sample Instrument" in prompt
    assert "Q1 (1-7): Tries new things." in prompt
    assert "JSON array" in prompt


def test_prompt_lists_items_in_the_order_it_is_given_them(instrument):
    questions = list(instrument.questions.order_by("question_id"))

    prompt = build_evaluation_prompt(instrument, questions)

    assert prompt.index("Q1") < prompt.index("Q2") < prompt.index("Q3")
