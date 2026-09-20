from io import StringIO
import json
from pathlib import Path

from django.core.management import call_command
from django.core.management.base import CommandError
import pytest

from core.models import Framework, Question, QuestionnaireResponse, Target
from core.scraper import queue, tasks

pytestmark = pytest.mark.django_db

FIXTURE = Path(__file__).parent / "fixtures" / "sample_instrument.json"


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


def test_load_questionnaire_creates_the_instrument():
    stdout = StringIO()

    call_command("load_questionnaire", FIXTURE, stdout=stdout)

    framework = Framework.objects.get(slug="sample-instrument")
    assert framework.traits.count() == 2
    assert framework.questions.count() == 3
    assert framework.questions.get(question_id="Q3").reverse_scored is True
    assert framework.citation.startswith("Test fixture")
    assert "3 items created" in stdout.getvalue()


def test_load_questionnaire_updates_items_in_place():
    call_command("load_questionnaire", FIXTURE, stdout=StringIO())
    Question.objects.filter(question_id="Q1").update(text="stale wording")

    call_command("load_questionnaire", FIXTURE, stdout=StringIO())

    assert Question.objects.filter(question_id="Q1").count() == 1
    assert Question.objects.get(question_id="Q1").text == "Tries new things."


def test_load_questionnaire_removes_items_absent_from_the_file(tmp_path):
    call_command("load_questionnaire", FIXTURE, stdout=StringIO())
    shortened = json.loads(FIXTURE.read_text(encoding="utf-8"))
    shortened["items"] = shortened["items"][:2]
    path = tmp_path / "shortened.json"
    path.write_text(json.dumps(shortened), encoding="utf-8")

    call_command("load_questionnaire", path, stdout=StringIO())

    assert Question.objects.filter(question_id="Q3").exists() is False


def test_load_questionnaire_keeps_items_that_already_have_answers(
    instrument,
    target,
    tmp_path,
):
    question = instrument.questions.get(question_id="Q3")
    QuestionnaireResponse.objects.create(target=target, question=question, score=4)
    shortened = json.loads(FIXTURE.read_text(encoding="utf-8"))
    shortened["items"] = shortened["items"][:2]

    call_command("load_questionnaire", _write(tmp_path, shortened))

    assert Question.objects.filter(question_id="Q3").exists()


def _write(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "instrument.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_load_questionnaire_rejects_undeclared_traits(tmp_path):
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document["items"][0]["trait"] = "not-declared"
    path = _write(tmp_path, document)

    with pytest.raises(CommandError):
        call_command("load_questionnaire", path)

    assert Framework.objects.count() == 0


def test_load_questionnaire_rejects_unknown_fields(tmp_path):
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document["items"][0]["weight"] = 2
    path = _write(tmp_path, document)

    with pytest.raises(CommandError):
        call_command("load_questionnaire", path)


def test_load_questionnaire_rejects_broken_json(tmp_path):
    path = tmp_path / "instrument.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(CommandError):
        call_command("load_questionnaire", path)


def test_load_questionnaire_rejects_an_inverted_scale(tmp_path):
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document["items"][0]["min_score"] = 5
    document["items"][0]["max_score"] = 1
    path = _write(tmp_path, document)

    with pytest.raises(CommandError):
        call_command("load_questionnaire", path)


def test_run_target_runs_in_the_foreground(monkeypatch):
    target = Target.objects.create(seed_username="seed_user")
    stdout = StringIO()

    async def _pipeline(target_id: int) -> None:
        return None

    monkeypatch.setattr(tasks, "_run_pipeline", _pipeline)

    call_command("run_target", target.pk, stdout=stdout)

    target.refresh_from_db()
    assert target.attempts == 1
    assert target.status == Target.Status.SCRAPING
    assert f"Target {target.pk} is scraping" in stdout.getvalue()


def test_run_target_reports_a_missing_target():
    with pytest.raises(CommandError):
        call_command("run_target", 4321)
