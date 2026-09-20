from io import StringIO
import json

from django.core.management import call_command
from django.core.management.base import CommandError
import pytest

from core.models import DiscoveredAccount, ProfileResult, Target

pytestmark = pytest.mark.django_db


def test_list_frameworks_reports_what_is_loaded(instrument):
    stdout = StringIO()

    call_command("list_frameworks", stdout=stdout)

    output = stdout.getvalue()
    assert "sample-instrument" in output
    assert "traits=2" in output
    assert "items=3" in output


def test_list_frameworks_says_when_nothing_is_loaded():
    stdout = StringIO()

    call_command("list_frameworks", stdout=stdout)

    assert "No instruments loaded" in stdout.getvalue()


def test_add_target_creates_a_pending_target():
    stdout = StringIO()

    call_command("add_target", "seed_user", stdout=stdout)

    target = Target.objects.get()
    assert target.seed_username == "seed_user"
    assert target.status == Target.Status.PENDING
    assert f"Added target {target.pk}" in stdout.getvalue()


def test_add_target_refuses_a_username_that_is_already_running():
    Target.objects.create(seed_username="seed_user", status=Target.Status.SCRAPING)

    with pytest.raises(CommandError):
        call_command("add_target", "seed_user")


def test_add_target_rejects_an_empty_username():
    with pytest.raises(CommandError):
        call_command("add_target", "   ")


def test_list_targets_prints_status_attempts_and_error():
    Target.objects.create(
        seed_username="seed_user",
        status=Target.Status.FAILED,
        last_error="every platform was blocked",
    )
    stdout = StringIO()

    call_command("list_targets", stdout=stdout)

    output = stdout.getvalue()
    assert "seed_user" in output
    assert "failed" in output
    assert "attempts=0" in output
    assert "last error: every platform was blocked" in output


def test_report_target_prints_scores_and_account_evidence(instrument, target):
    DiscoveredAccount.objects.create(
        target=target,
        platform_name="github",
        url="https://github.com/seed_user",
        username="seed_user",
        display_name="Seed User",
        confidence=0.4,
        signals=["existence_proven", "handle_matches_seed"],
    )
    ProfileResult.objects.create(
        target=target,
        framework=instrument,
        score_data={
            "openness": {"name": "Openness", "average": 4.0, "answers": 2},
            "caution": {"name": "Caution", "average": None, "answers": 0},
        },
    )
    stdout = StringIO()

    call_command("report_target", target.pk, stdout=stdout)

    output = stdout.getvalue()
    assert f"Target {target.pk}: seed_user" in output
    assert "Sample Instrument" in output
    assert "Openness: 4.00 (2 answer(s))" in output
    assert "Caution: no answers (0 answer(s))" in output
    assert "confidence 0.40" in output
    assert "handle_matches_seed" in output


def test_report_target_marks_instruments_that_never_ran(instrument, target):
    stdout = StringIO()

    call_command("report_target", target.pk, stdout=stdout)

    assert "not evaluated" in stdout.getvalue()


def test_report_target_prints_json_when_asked(instrument, target):
    stdout = StringIO()

    call_command("report_target", target.pk, "--json", stdout=stdout)

    payload = json.loads(stdout.getvalue())
    assert payload["target"]["username"] == "seed_user"
    assert payload["instruments"][0]["slug"] == "sample-instrument"
    assert payload["instruments"][0]["evaluated"] is False
    assert payload["accounts"] == []


def test_report_target_writes_the_output_to_a_file(instrument, target, tmp_path):
    path = tmp_path / "report.json"

    call_command(
        "report_target",
        target.pk,
        "--json",
        "--out",
        path,
        stdout=StringIO(),
    )

    written = json.loads(path.read_text(encoding="utf-8"))
    assert written["target"]["username"] == "seed_user"
    assert written["instruments"][0]["slug"] == "sample-instrument"


def test_report_target_reports_a_missing_target():
    with pytest.raises(CommandError):
        call_command("report_target", 4321)
