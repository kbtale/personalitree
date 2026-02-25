import logging
import os
from datetime import timedelta

from django.utils import timezone

logger = logging.getLogger(__name__)


def _get_config(key: str, default: str) -> str:
    """Read from Settings model first, fallback to env var."""
    try:
        from core.models import Settings
        setting = Settings.objects.filter(key=key).first()
        if setting and setting.value:
            return setting.value
    except Exception:
        pass
    return os.environ.get(key, default)


def prepare_llm_payload(target_id: int) -> str:
    """
    Aggregate, filter, and truncate all RawScrape text for a target.
    Returns a single string ready for the LLM prompt.
    """
    from core.models import RawScrape

    max_posts = int(_get_config("MAX_SCRAPE_POSTS", "100"))
    timeframe_months = int(_get_config("SCRAPE_TIMEFRAME_MONTHS", "12"))
    max_tokens = int(_get_config("MAX_LLM_TOKENS", "8000"))

    cutoff = timezone.now() - timedelta(days=timeframe_months * 30)

    scrapes = (
        RawScrape.objects
        .filter(target_id=target_id, scraped_at__gte=cutoff)
        .order_by("-scraped_at")[:max_posts]
    )

    chunks = []
    for scrape in scrapes:
        if scrape.raw_text_dump.strip():
            header = f"[{scrape.platform_name}]"
            chunks.append(f"{header}\n{scrape.raw_text_dump.strip()}")

    payload = "\n\n---\n\n".join(chunks)

    estimated_tokens = len(payload) // 4
    if estimated_tokens > max_tokens:
        char_limit = max_tokens * 4
        payload = payload[:char_limit]
        logger.info(
            "Payload truncated from ~%d to ~%d tokens for target_id=%d",
            estimated_tokens,
            max_tokens,
            target_id,
        )

    logger.info(
        "Payload prepared for target_id=%d: %d scrapes, ~%d tokens",
        target_id,
        len(chunks),
        len(payload) // 4,
    )

    return payload
