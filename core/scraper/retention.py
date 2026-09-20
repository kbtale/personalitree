"""
Retention policy for the raw text collected while scraping.
"""

import logging

from core.constants import DEFAULT_RETENTION_MODE, ConfigKey, RetentionMode
from core.models import RawScrape
from core.utils.config import get_config

logger = logging.getLogger(__name__)


def purge_target_scrapes(target_id: int) -> int:
    """Clear the stored text and metadata of a target's scrapes."""
    purged = RawScrape.objects.filter(target_id=target_id).update(
        raw_text_dump="",
        metadata_json={},
    )
    logger.info("Purged raw text of %d scrape(s) for target %d", purged, target_id)
    return purged


def apply_retention(target_id: int) -> None:
    """Purge a target's raw text when the configured retention mode is ephemeral."""
    mode = get_config(ConfigKey.RETENTION_MODE, DEFAULT_RETENTION_MODE)
    if mode != RetentionMode.EPHEMERAL:
        return
    purge_target_scrapes(target_id)
