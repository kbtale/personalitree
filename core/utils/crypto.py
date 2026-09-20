"""
Symmetric encryption for values stored in the database.
"""

import logging

from cryptography.fernet import Fernet, InvalidToken

from core.constants import ConfigKey
from core.exceptions import ConfigurationError
from core.utils.config import get_config

logger = logging.getLogger(__name__)

FERNET_TOKEN_PREFIX = "gAAAAA"


def get_fernet() -> Fernet:
    """Build a Fernet from the configured key, failing when it is unusable."""
    key = get_config(ConfigKey.FIELD_ENCRYPTION_KEY, "")
    if not key:
        raise ConfigurationError(f"{ConfigKey.FIELD_ENCRYPTION_KEY} is not configured")
    try:
        return Fernet(key.encode("utf-8"))
    except ValueError as exc:
        raise ConfigurationError(
            f"{ConfigKey.FIELD_ENCRYPTION_KEY} is not a valid Fernet key"
        ) from exc


def encrypt_value(value: str) -> str:
    """Encrypt a plaintext value for storage."""
    return get_fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_value(value: str) -> str:
    """Decrypt a stored value, passing through plaintext written before encryption."""
    if not value.startswith(FERNET_TOKEN_PREFIX):
        logger.warning("Reading an unencrypted value; run encrypt_burner_passwords")
        return value
    try:
        return get_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken as exc:
        raise ConfigurationError(
            f"{ConfigKey.FIELD_ENCRYPTION_KEY} cannot decrypt the stored value"
        ) from exc
