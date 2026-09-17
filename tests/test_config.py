import pytest

from core.constants import ConfigKey
from core.models import Settings
from core.utils.config import get_config

pytestmark = pytest.mark.django_db

KEY = ConfigKey.MAX_LLM_TOKENS


def test_stored_row_takes_precedence_over_environment(monkeypatch):
    monkeypatch.setenv(KEY, "1234")
    Settings.objects.create(key=KEY, value="4321")

    assert get_config(KEY, "8000") == "4321"


def test_environment_is_used_when_no_row_exists(monkeypatch):
    monkeypatch.setenv(KEY, "1234")

    assert get_config(KEY, "8000") == "1234"


def test_default_is_returned_when_neither_source_is_set(monkeypatch):
    monkeypatch.delenv(KEY, raising=False)

    assert get_config(KEY, "8000") == "8000"


def test_blank_row_falls_back_to_environment(monkeypatch):
    monkeypatch.setenv(KEY, "1234")
    Settings.objects.create(key=KEY, value="")

    assert get_config(KEY, "8000") == "1234"
