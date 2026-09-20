from io import StringIO
import json
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
import pytest

from core.constants import BIG_FIVE_TRAITS, Framework
from core.models import Question, Target
from core.scraper import queue

pytestmark = pytest.mark.django_db

FIXTURE = Path(__file__).parent / "fixtures" / "big_five_sample.json"


def test_queue_scrape_dispatches_the_task(monkeypatch):
    target = Target.objects.create(seed_username="seed_user")
    monkeypatch.setattr(queue, "async_task", lambda *args, **kwargs: "task-id")
    stdout = StringIO()

    call_command("queue_scrape", target.pk, stdout=stdout)

    target.refresh_from_db()
    assert target.status == Target.Status.QUEUED
    assert "task-id" in stdout.getvalue()


def test_queue_scrape_reports_a_missing_target():
    with pytest.raises(CommandError):
        call_command("queue_scrape", 4321)


def test_queue_scrape_refuses_a_target_that_is_already_active(monkeypatch):
    target = Target.objects.create(
        seed_username="seed_user",
        status=Target.Status.SCRAPING,
    )
    monkeypatch.setattr(queue, "async_task", lambda *args, **kwargs: "task-id")

    with pytest.raises(CommandError):
        call_command("queue_scrape", target.pk)


def test_reset_target_clears_the_attempt_history():
    target = Target.objects.create(
        seed_username="seed_user",
        status=Target.Status.FAILED,
    )
    Target.objects.filter(id=target.pk).update(
        attempts=2,
        last_error="every platform was blocked",
    )
    stdout = StringIO()

    call_command("reset_target", target.pk, stdout=stdout)

    target.refresh_from_db()
    assert target.status == Target.Status.PENDING
    assert target.attempts == 0
    assert target.last_error == ""
    assert "reset" in stdout.getvalue()


def test_load_questionnaire_creates_the_bank():
    stdout = StringIO()

    call_command("load_questionnaire", FIXTURE, stdout=stdout)

    assert Question.objects.count() == 3
    assert Question.objects.get(question_id="Q2").reverse_scored is True
    assert "3 created" in stdout.getvalue()


def test_load_questionnaire_updates_existing_items():
    call_command("load_questionnaire", FIXTURE, stdout=StringIO())
    Question.objects.filter(question_id="Q1").update(text="stale wording")

    call_command("load_questionnaire", FIXTURE, stdout=StringIO())

    assert Question.objects.count() == 3
    assert Question.objects.get(question_id="Q1").text == "I enjoy trying new things."


def test_load_questionnaire_rejects_an_unknown_trait(tmp_path):
    path = tmp_path / "bank.json"
    path.write_text(
        json.dumps(
            [
                {
                    "question_id": "Q1",
                    "framework_name": Framework.BIG_FIVE,
                    "trait": "Charisma",
                    "text": "I light up a room.",
                }
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(CommandError):
        call_command("load_questionnaire", path)

    assert Question.objects.count() == 0


def test_load_questionnaire_reports_broken_json(tmp_path):
    path = tmp_path / "bank.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(CommandError):
        call_command("load_questionnaire", path)


def test_load_questionnaire_requires_the_known_fields(tmp_path):
    path = tmp_path / "bank.json"
    path.write_text(
        json.dumps([{"question_id": "Q1", "framework_name": Framework.BIG_FIVE}]),
        encoding="utf-8",
    )

    with pytest.raises(CommandError):
        call_command("load_questionnaire", path)


def test_loaded_question_accepts_the_framework_traits():
    call_command("load_questionnaire", FIXTURE, stdout=StringIO())

    question = Question.objects.get(question_id="Q3")
    assert question.trait in BIG_FIVE_TRAITS
