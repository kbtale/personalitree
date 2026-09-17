import pytest

from core.models import Settings
from core.utils.config import get_config

pytestmark = pytest.mark.django_db


def test_stored_row_takes_precedence_over_environment(monkeypatch):
    monkeypatch.setenv("MAX_LLM_TOKENS", "1234")
    Settings.objects.create(key="MAX_LLM_TOKENS", value="4321")

    assert get_config("MAX_LLM_TOKENS", "8000") == "4321"


def test_environment_is_used_when_no_row_exists(monkeypatch):
    monkeypatch.setenv("MAX_LLM_TOKENS", "1234")

    assert get_config("MAX_LLM_TOKENS", "8000") == "1234"


def test_default_is_returned_when_neither_source_is_set(monkeypatch):
    monkeypatch.delenv("MAX_LLM_TOKENS", raising=False)

    assert get_config("MAX_LLM_TOKENS", "8000") == "8000"


def test_blank_row_falls_back_to_environment(monkeypatch):
    monkeypatch.setenv("MAX_LLM_TOKENS", "1234")
    Settings.objects.create(key="MAX_LLM_TOKENS", value="")

    assert get_config("MAX_LLM_TOKENS", "8000") == "1234"
