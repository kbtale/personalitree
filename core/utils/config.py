"""
Reads from the Settings model with an environment variable fallback.
"""
import os

def get_config(key: str, default: str) -> str:
    try:
        from core.models import Settings
        setting = Settings.objects.filter(key=key).first()
        if setting and setting.value:
            return setting.value
    except Exception:
        pass
    return os.environ.get(key, default)
