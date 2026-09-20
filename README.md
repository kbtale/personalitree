# personalitree

## Development

PersonaliTree targets Python 3.12 (see the `Dockerfile`). All tooling configuration lives
in `pyproject.toml`: Ruff, Black, pytest, and coverage.

### Setup

```bash
python -m venv .venv
.venv/Scripts/activate      # Windows
source .venv/bin/activate   # Linux / macOS

pip install -r requirements.txt
pip install --group dev     # requires pip >= 25.1
```

On older pip versions, install the dev tools explicitly:

```bash
pip install "ruff>=0.12.0" "black>=25.1.0" pytest pytest-cov pytest-django
```

### Checks

```bash
ruff check .             # lint
ruff format --check .    # formatting
black --check .          # formatting, second opinion
pytest                   # test suite with coverage
python manage.py check   # Django sanity check
```

`pytest` collects `tests/` against `personalitree.settings` and needs no Playwright
browsers; browsers are only required to run the scraper itself.

### Running a scrape

```bash
python manage.py migrate
python manage.py queue_scrape <target_id>   # or the "Queue scraping" admin action
python manage.py qcluster                   # second shell, consumes the queue
```

The target walks `PENDING -> QUEUED -> SCRAPING -> COMPLETED`. A run that keeps failing ends on
`FAILED` with the reason in `last_error`; fix the cause and run
`python manage.py reset_target <target_id>` to clear the attempt history before queueing it again.
Inside Docker the worker is `docker compose run --rm worker python manage.py qcluster`.

