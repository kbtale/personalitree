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
