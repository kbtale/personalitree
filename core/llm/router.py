"""
Routes requests to OpenAI, Anthropic, or Google Generative AI based on configuration.
"""
import logging
from core.utils.config import get_config

logger = logging.getLogger(__name__)

async def generate_llm_response(system_prompt: str, user_payload: str) -> str:
    provider = get_config("LLM_PROVIDER", "openai").lower()

    if provider == "openai":
        return await _query_openai(system_prompt, user_payload)
    elif provider == "anthropic":
        return await _query_anthropic(system_prompt, user_payload)
    elif provider == "google":
        return await _query_google(system_prompt, user_payload)
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {provider}")

async def _query_openai(system_prompt: str, user_payload: str) -> str:
    from openai import AsyncOpenAI
    api_key = get_config("OPENAI_API_KEY", "")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is missing")

    client = AsyncOpenAI(api_key=api_key)
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_payload},
        ],
        temperature=0.0,
    )
    return response.choices[0].message.content or ""

async def _query_anthropic(system_prompt: str, user_payload: str) -> str:
    from anthropic import AsyncAnthropic
    api_key = get_config("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY is missing")

    client = AsyncAnthropic(api_key=api_key)
    response = await client.messages.create(
        model="claude-3-5-haiku-20241022",
        system=system_prompt,
        messages=[
            {"role": "user", "content": user_payload},
        ],
        max_tokens=2048,
        temperature=0.0,
    )
    return response.content[0].text

async def _query_google(system_prompt: str, user_payload: str) -> str:
    import google.generativeai as genai
    import asyncio
    api_key = get_config("GOOGLE_API_KEY", "")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY is missing")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash",
        system_instruction=system_prompt,
        generation_config={"temperature": 0.0}
    )
    response = await asyncio.to_thread(
        model.generate_content,
        user_payload,
    )
    return response.text
