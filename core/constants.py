"""Canonical constants shared across the project."""

from enum import StrEnum

from django.db import models


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
    FIELD_ENCRYPTION_KEY = "FIELD_ENCRYPTION_KEY"
    MAX_SCRAPE_POSTS = "MAX_SCRAPE_POSTS"
    SCRAPE_TIMEFRAME_MONTHS = "SCRAPE_TIMEFRAME_MONTHS"
    MAX_LLM_TOKENS = "MAX_LLM_TOKENS"
    RETENTION_MODE = "RETENTION_MODE"


class RetentionMode(StrEnum):
    """How long raw scrape text is kept after a run."""

    PERSISTENT = "persistent"
    EPHEMERAL = "ephemeral"


class LLMProvider(StrEnum):
    """Providers supported by the LLM router."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class Framework(models.TextChoices):
    """Personality framework a question bank belongs to."""

    BIG_FIVE = "Big Five", "Big Five"


DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_ANTHROPIC_MODEL = "claude-3-5-haiku-20241022"
DEFAULT_GOOGLE_MODEL = "gemini-1.5-flash"

BIG_FIVE_TRAITS = (
    "Openness",
    "Conscientiousness",
    "Extraversion",
    "Agreeableness",
    "Neuroticism",
)

FRAMEWORK_TRAITS: dict[str, tuple[str, ...]] = {
    Framework.BIG_FIVE: BIG_FIVE_TRAITS,
}

SCORE_MIN = 1
SCORE_MAX = 5

HTTP_OK = 200
CHARS_PER_TOKEN_ESTIMATE = 4

MAX_SCRAPE_ATTEMPTS = 2
SCRAPE_TASK_TIMEOUT_SECONDS = 3600
DEFAULT_RETENTION_MODE = RetentionMode.PERSISTENT

PAGE_TIMEOUT_MS = 15000
MAX_DISCOVERY_CANDIDATES = 50
MAX_DISCOVERY_DEPTH = 2
MAX_SCRAPE_ACCOUNTS = 100
