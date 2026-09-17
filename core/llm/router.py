"""
Routes requests to OpenAI, Anthropic, or Google Generative AI based on configuration.
"""

import asyncio
from collections.abc import Awaitable, Callable
import logging

from core.constants import (
    DEFAULT_ANTHROPIC_MODEL,
    DEFAULT_GOOGLE_MODEL,
    DEFAULT_OPENAI_MODEL,
    ConfigKey,
    LLMProvider,
)
from core.exceptions import (
    LLMProviderError,
    MissingCredentialError,
    UnsupportedProviderError,
)
from core.utils.config import get_config

logger = logging.getLogger(__name__)

ProviderHandler = Callable[[str, str], Awaitable[str]]


async def generate_llm_response(system_prompt: str, user_payload: str) -> str:
    provider = await asyncio.to_thread(
        get_config, ConfigKey.LLM_PROVIDER, LLMProvider.OPENAI
    )

    handler = _PROVIDER_HANDLERS.get(provider.lower())
    if handler is None:
        raise UnsupportedProviderError(provider)

    return await handler(system_prompt, user_payload)


async def _query_openai(system_prompt: str, user_payload: str) -> str:
    from openai import APIError, AsyncOpenAI

    api_key = await asyncio.to_thread(get_config, ConfigKey.OPENAI_API_KEY, "")
    if not api_key:
        raise MissingCredentialError(f"{ConfigKey.OPENAI_API_KEY} is not configured")

    model = await asyncio.to_thread(
        get_config, ConfigKey.OPENAI_MODEL, DEFAULT_OPENAI_MODEL
    )
    client = AsyncOpenAI(api_key=api_key)
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_payload},
            ],
            temperature=0.0,
        )
    except APIError as exc:
        raise LLMProviderError(str(exc)) from exc
    return response.choices[0].message.content or ""


async def _query_anthropic(system_prompt: str, user_payload: str) -> str:
    from anthropic import APIError, AsyncAnthropic

    api_key = await asyncio.to_thread(get_config, ConfigKey.ANTHROPIC_API_KEY, "")
    if not api_key:
        raise MissingCredentialError(f"{ConfigKey.ANTHROPIC_API_KEY} is not configured")

    model = await asyncio.to_thread(
        get_config, ConfigKey.ANTHROPIC_MODEL, DEFAULT_ANTHROPIC_MODEL
    )
    client = AsyncAnthropic(api_key=api_key)
    try:
        response = await client.messages.create(
            model=model,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_payload},
            ],
            max_tokens=2048,
            temperature=0.0,
        )
    except APIError as exc:
        raise LLMProviderError(str(exc)) from exc
    return response.content[0].text


async def _query_google(system_prompt: str, user_payload: str) -> str:
    from google.api_core.exceptions import GoogleAPIError
    import google.generativeai as genai

    api_key = await asyncio.to_thread(get_config, ConfigKey.GOOGLE_API_KEY, "")
    if not api_key:
        raise MissingCredentialError(f"{ConfigKey.GOOGLE_API_KEY} is not configured")

    model_name = await asyncio.to_thread(
        get_config, ConfigKey.GOOGLE_MODEL, DEFAULT_GOOGLE_MODEL
    )
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=system_prompt,
        generation_config={"temperature": 0.0},
    )
    try:
        response = await asyncio.to_thread(
            model.generate_content,
            user_payload,
        )
    except (GoogleAPIError, genai.types.BlockedPromptException) as exc:
        raise LLMProviderError(str(exc)) from exc
    return response.text


_PROVIDER_HANDLERS: dict[str, ProviderHandler] = {
    LLMProvider.OPENAI.value: _query_openai,
    LLMProvider.ANTHROPIC.value: _query_anthropic,
    LLMProvider.GOOGLE.value: _query_google,
}
