"""
Reads from the Settings model with an environment variable fallback.
"""

import os

from django.core.exceptions import (
    AppRegistryNotReady,
    ImproperlyConfigured,
    SynchronousOnlyOperation,
)
from django.db.utils import OperationalError, ProgrammingError

from core.constants import ConfigKey


def get_config(key: ConfigKey, default: str) -> str:
    try:
        from core.models import Settings

        setting = Settings.objects.filter(key=key).first()
    except (
        AppRegistryNotReady,
        ImproperlyConfigured,
        OperationalError,
        ProgrammingError,
        SynchronousOnlyOperation,
    ):
        return os.environ.get(key, default)
    if setting and setting.value:
        return setting.value
    return os.environ.get(key, default)
