import asyncio
from unittest.mock import AsyncMock

import pytest

from core.constants import ConfigKey, LLMProvider
from core.exceptions import MissingCredentialError, UnsupportedProviderError
from core.llm import router
from core.models import Settings


def _stub_config(monkeypatch, **values):
    def _get_config(key, default):
        return values.get(str(key), default)

    monkeypatch.setattr(router, "get_config", _get_config)


def test_unsupported_provider_is_rejected(monkeypatch):
    _stub_config(monkeypatch, LLM_PROVIDER="mystery")

    with pytest.raises(UnsupportedProviderError):
        asyncio.run(router.generate_llm_response("system", "payload"))


def test_missing_api_key_is_reported(monkeypatch):
    _stub_config(monkeypatch, LLM_PROVIDER=LLMProvider.OPENAI, OPENAI_API_KEY="")

    with pytest.raises(MissingCredentialError):
        asyncio.run(router.generate_llm_response("system", "payload"))


@pytest.mark.parametrize(
    ("provider", "handler_name"),
    [
        (LLMProvider.OPENAI, "_query_openai"),
        (LLMProvider.ANTHROPIC, "_query_anthropic"),
        (LLMProvider.GOOGLE, "_query_google"),
    ],
)
def test_request_is_dispatched_to_the_selected_provider(
    monkeypatch, provider, handler_name
):
    handler = AsyncMock(return_value="response text")
    monkeypatch.setitem(router._PROVIDER_HANDLERS, provider.value, handler)
    _stub_config(monkeypatch, LLM_PROVIDER=provider)

    result = asyncio.run(router.generate_llm_response("system", "payload"))

    assert result == "response text"
    handler.assert_awaited_once_with("system", "payload")


@pytest.mark.django_db(transaction=True)
def test_provider_is_read_from_settings_while_the_loop_runs(monkeypatch):
    Settings.objects.create(key=ConfigKey.LLM_PROVIDER, value=LLMProvider.ANTHROPIC)
    handler = AsyncMock(return_value="response text")
    monkeypatch.setitem(router._PROVIDER_HANDLERS, LLMProvider.ANTHROPIC.value, handler)

    result = asyncio.run(router.generate_llm_response("system", "payload"))

    assert result == "response text"
    handler.assert_awaited_once_with("system", "payload")
