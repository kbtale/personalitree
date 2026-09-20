# ============================================================
# PersonaliTree - Dockerfile
# Builds the Python environment from uv.lock, with Playwright
# ============================================================

FROM python:3.12-slim-bookworm

# ----- Environment tweaks -----
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# ----- OS-level dependencies -----
# Build essentials + libraries required by psycopg2 and Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
        wget \
        gnupg \
    && rm -rf /var/lib/apt/lists/*

# ----- uv (pinned to the version the lock was generated with) -----
COPY --from=ghcr.io/astral-sh/uv:0.11.6 /uv /usr/local/bin/uv

# ----- Python dependencies, exactly as locked -----
WORKDIR /app

COPY pyproject.toml uv.lock /app/
RUN uv sync --frozen --no-dev

# ----- Playwright headless browsers -----
# Install browser binaries + their OS-level dependencies
RUN playwright install --with-deps chromium

# ----- Copy project source -----
COPY . /app

# ----- Expose default Django port -----
EXPOSE 8000

# Default command (overridden per service in docker-compose)
CMD ["gunicorn", "personalitree.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
