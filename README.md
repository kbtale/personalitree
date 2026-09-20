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

### Credential storage

Burner account passwords are encrypted at rest with Fernet, so `FIELD_ENCRYPTION_KEY` has to be set
before any credential is stored:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Changing the key makes stored passwords undecryptable; the application reports that instead of
returning garbage. Rows written before encryption existed are read as plaintext with a warning and
are converted by `python manage.py encrypt_burner_passwords`.

### Question bank

The evaluation prompt is built from the questions stored in the database, so load a bank before
running a scrape:

```bash
python manage.py load_questionnaire path/to/questions.json
```

The file is a JSON array; `question_id`, `framework_name`, `trait` and `text` are required, while
`reverse_scored`, `min_score` and `max_score` are optional (defaults: `false`, `1`, `5`):

```json
[
  {
    "question_id": "Q1",
    "framework_name": "Big Five",
    "trait": "Openness",
    "text": "I enjoy trying new things.",
    "reverse_scored": false
  }
]
```

Items are upserted by `framework_name` and `question_id`, so re-running the command after a wording
change updates the item without touching answers already recorded.

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

