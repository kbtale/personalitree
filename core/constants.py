"""Canonical constants shared across the project."""

from enum import StrEnum


class ConfigKey(StrEnum):
    """Configuration keys resolved through the Settings model and environment."""

    LLM_PROVIDER = "LLM_PROVIDER"
    OPENAI_API_KEY = "OPENAI_API_KEY"
    ANTHROPIC_API_KEY = "ANTHROPIC_API_KEY"
    GOOGLE_API_KEY = "GOOGLE_API_KEY"
    OPENAI_MODEL = "OPENAI_MODEL"
    ANTHROPIC_MODEL = "ANTHROPIC_MODEL"
    GOOGLE_MODEL = "GOOGLE_MODEL"
    PROXY_URL = "PROXY_URL"
    MAX_SCRAPE_POSTS = "MAX_SCRAPE_POSTS"
    SCRAPE_TIMEFRAME_MONTHS = "SCRAPE_TIMEFRAME_MONTHS"
    MAX_LLM_TOKENS = "MAX_LLM_TOKENS"


class LLMProvider(StrEnum):
    """Providers supported by the LLM router."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_ANTHROPIC_MODEL = "claude-3-5-haiku-20241022"
DEFAULT_GOOGLE_MODEL = "gemini-1.5-flash"

FRAMEWORK_BIG_FIVE = "Big Five"
BIG_FIVE_TRAITS = (
    "Openness",
    "Conscientiousness",
    "Extraversion",
    "Agreeableness",
    "Neuroticism",
)

HTTP_OK = 200
CHARS_PER_TOKEN_ESTIMATE = 4

MAX_SCRAPE_ATTEMPTS = 2
SCRAPE_TASK_TIMEOUT_SECONDS = 3600
