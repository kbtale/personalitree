"""
PersonaliTree Settings
======================
Fully environment-driven configuration.
All secrets and deployment knobs are read from environment variables
(loaded from the .env file at the project root via python-dotenv).

Docs: https://docs.djangoproject.com/en/5.1/ref/settings/
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# ============================================================
# 0. Paths & Environment Bootstrap
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# Load the .env file sitting next to manage.py
load_dotenv(BASE_DIR / ".env")


def env(key: str, default: str = "") -> str:
    """Shorthand: read an env var with an optional default."""
    return os.environ.get(key, default)


def env_bool(key: str, default: bool = False) -> bool:
    """Read an env var as a boolean (true/1/yes → True)."""
    return env(key, str(default)).lower() in ("true", "1", "yes")


def env_list(key: str, default: str = "") -> list[str]:
    """Read a comma-separated env var into a list of strings."""
    raw = env(key, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


# ============================================================
# 1. Security
# ============================================================

SECRET_KEY = env("DJANGO_SECRET_KEY", "insecure-dev-key-change-me")

DEBUG = env_bool("DJANGO_DEBUG", default=True)

ALLOWED_HOSTS: list[str] = env_list(
    "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0"
)


# ============================================================
# 2. Application Registry
# ============================================================

INSTALLED_APPS = [
    # --- Django Core ---
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # --- Third-Party ---
    "django_q",
    # --- Project Apps (added as they are created) ---
    # "core",
]


# ============================================================
# 3. Middleware
# ============================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# ============================================================
# 4. URL & Template Configuration
# ============================================================

ROOT_URLCONF = "personalitree.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "personalitree.wsgi.application"
ASGI_APPLICATION = "personalitree.asgi.application"


# ============================================================
# 5. Database, PostgreSQL via environment variables
# ============================================================
# The 'db' service hostname comes from docker-compose service name.

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "personalitree"),
        "USER": env("POSTGRES_USER", "personalitree"),
        "PASSWORD": env("POSTGRES_PASSWORD", "personalitree"),
        "HOST": env("POSTGRES_HOST", "db"),       # docker-compose service name
        "PORT": env("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 600,                      # keep connections alive 10 min
        "OPTIONS": {
            "connect_timeout": 10,
        },
    }
}


# ============================================================
# 6. Django Q2, Async Task Queue (ORM Broker)
# ============================================================
# The 'worker' container runs `python manage.py qcluster`.

Q_CLUSTER = {
    "name": "personalitree",
    "workers": int(env("Q_WORKERS", "2")),
    "recycle": 500,               # restart worker after N tasks (leak guard)
    "timeout": 600,               # max seconds a single task may run
    "retry": 660,                 # retry window (must be > timeout)
    "compress": True,             # gzip large payloads
    "save_limit": 250,            # keep last N successful results in DB
    "queue_limit": 50,            # max tasks waiting in queue
    "label": "PersonaliTree Q",
    "orm": "default",             # use the 'default' database as broker
    "catch_up": False,            # don't replay missed scheduled tasks on boot
}


# ============================================================
# 7. Password Validation
# ============================================================

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ============================================================
# 8. Internationalization & Timezone
# ============================================================

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True


# ============================================================
# 9. Static & Media Files
# ============================================================

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"


# ============================================================
# 10. Miscellaneous
# ============================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Logging — structured, container-friendly (stdout)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": env("DJANGO_LOG_LEVEL", "INFO"),
            "propagate": False,
        },
        "django_q": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
