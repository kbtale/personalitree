# ============================================================
# PersonaliTree – Dockerfile
# Builds the Python environment with Playwright browser deps
# ============================================================

FROM python:3.12-slim-bookworm

# ----- Environment tweaks -----
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# ----- OS-level dependencies -----
# Build essentials + libraries required by psycopg2 and Playwright
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
        wget \
        gnupg \
    && rm -rf /var/lib/apt/lists/*

# ----- Python dependencies -----
WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ----- Playwright headless browsers -----
# Install browser binaries + their OS-level dependencies
RUN playwright install --with-deps chromium

# ----- Copy project source -----
COPY . /app

# ----- Expose default Django port -----
EXPOSE 8000

# Default command (overridden per service in docker-compose)
CMD ["gunicorn", "personalitree.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
