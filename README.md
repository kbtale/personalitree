# personalitree

## Development

PersonaliTree targets Python 3.12 (see the `Dockerfile`). All tooling configuration lives
in `pyproject.toml`: Ruff, Black, pytest, and coverage.

Where things live:

- `personalitree/` - settings and URL config; no HTTP surface is exposed.
- `core/` - models, scraper, LLM pipeline, scoring and the management commands.
- `banks/` - instrument banks, loaded with `load_questionnaire`.
- `tests/` - the pytest suite.

### Setup

Dependencies are declared in `pyproject.toml` and pinned in `uv.lock`. Use
[uv](https://docs.astral.sh/uv/) so the environment matches the lock exactly:

```bash
uv sync            # runtime + dev dependencies into .venv
uv sync --frozen   # exactly what the lock says, which is what CI and Docker use
```

### Checks

```bash
uv run ruff check .             # lint
uv run ruff format --check .    # formatting
uv run black --check .          # formatting, second opinion
uv run pytest                   # test suite with coverage
uv run python manage.py check   # Django sanity check
uv run python manage.py makemigrations --check --dry-run   # no model drift
```

`pytest` collects `tests/` against `personalitree.settings` and needs no Playwright
browsers; browsers are only required to run the scraper itself.

### Retention

`RETENTION_MODE` decides what happens to raw profile text once a run finishes: `persistent` (the
default) keeps it in the database, `ephemeral` clears the text and metadata of every scrape for the
target as soon as the attempt ends, leaving the aggregates. `python manage.py purge_scrapes
<target_id>` clears a target's raw text on demand, whatever the mode.

### Credential storage

Burner account passwords are encrypted at rest with Fernet, so `FIELD_ENCRYPTION_KEY` has to be set
before any credential is stored:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Changing the key makes stored passwords undecryptable; the application reports that instead of
returning garbage. Rows written before encryption existed are read as plaintext with a warning and
are converted by `python manage.py encrypt_burner_passwords`.

### Identity evidence

A discovered account is only recorded when the platform proves the profile exists: the response is
200, the page did not redirect away from the profile URL, and none of the platform's not-found markers
appear in it. Platforms whose not-found page has no distinguishable marker fall back to a generic
marker list plus the status and URL checks, and the row records which checks ran.

Each row also carries `confidence`, the sum of the weights of the signals that were observed, and
`signals`, the names of those signals: `handle_matches_seed` (0.40), `display_name_matches_known`
(0.30), `bio_links_to_confirmed` (0.20) and `probed_from_confirmed_bio` (0.10). Nothing is assumed
beyond what the page showed, so a match with no corroboration sits at 0.00 rather than pretending to
be certain.

### Instruments

An instrument is a framework with its traits and items. Load one from a file:

```bash
python manage.py load_questionnaire banks/ipip-big-five-50.json
```

The file is a JSON object. `framework` needs `slug` and `name`, plus any of `description`, `citation`,
`source_url` and `is_active`. `traits` is a non-empty list of `slug`/`name` pairs, in the order the
instrument reads them, each optionally with `description` and the two sides of a dichotomy as
`high_label` and `low_label`; `items` is a non-empty list of `id`, `trait`, `text` with optional
`reverse_scored`, `min_score` and `max_score` (defaults `false`, `1` and `5`):

```json
{
  "framework": { "slug": "my-instrument", "name": "My Instrument" },
  "traits": [{ "slug": "curiosity", "name": "Curiosity" }],
  "items": [
    { "id": "Q1", "trait": "curiosity", "text": "Asks a lot of questions." }
  ]
}
```

The whole file is loaded in one transaction: a malformed file writes nothing and reports every problem
it can see. Items and traits are upserted by slug, and items the file no longer lists are removed
unless they already have answers, in which case they are kept and counted. Every active instrument is
evaluated for every target, so `is_active: false` keeps an instrument loaded without running it.

### Catalogue

Three instruments ship with the repo, each with its citation and source URL inside the file:

| Slug | Construct | Items | Source |
| --- | --- | --- | --- |
| `ipip-big-five-50` | Big Five: Extraversion, Agreeableness, Conscientiousness, Emotional Stability, Intellect/Imagination | 50 | Goldberg (1992), `ipip.ori.org/New_IPIP-50-item-scale.htm` |
| `mini-ipip6-24` | Big Six: Extraversion, Agreeableness, Conscientiousness, Neuroticism, Openness to Experience, Honesty-Humility | 24 | Milojev et al. (2013), `ipip.ori.org/MiniIPIP6Key.htm` |
| `oejts-1.2` | Jungian type: Extroversion, Intuition, Thinking and Perceiving against their opposite poles | 32 | Jorgenson (2015), `openpsychometrics.org/tests/OEJTS/` |

The two IPIP banks are third-person statements rated for agreement; the OEJTS is 32 bipolar pairs, each
rated 1-5 from one description to the other.

Load any of them with `python manage.py load_questionnaire banks/<file>.json`. Every active instrument is
evaluated for every target, so all three run unless you set `is_active: false` in the file, and loading a
file again updates the same rows instead of duplicating them.

`python manage.py list_frameworks` lists what is loaded: slug, name, trait and item counts, and whether
the instrument is active.

Each file keeps the keying of the page it came from:

| Bank | Items per trait | Direct | Reverse-scored |
| --- | --- | --- | --- |
| `ipip-big-five-50` | 10 | 26 | 24 |
| `mini-ipip6-24` | 4 | 9 | 15 |
| `oejts-1.2` | 8 | 17 | 15 |

All four Honesty-Humility items are reverse-scored, so a high score there means low entitlement rather
than agreement. The OEJTS reverses exactly the pairs its published key negates, which makes each
dichotomy's average equal to the published sum over eight: its cut of 24 of 40 is an average of 3.0, and
the four letters are read off the four averages. `report_target` prints them: each dichotomy shows the
letter it reads as, and the instrument gets a `type:` line with the letters joined, for example
`ISFJ`. An instrument whose traits declare no `high_label`/`low_label` prints neither, and a dichotomy
with no answers withholds the type rather than guessing a side. Anything you supply as a file loads
through the same validation.

### Running the tool

PersonaliTree is a single-user command line tool: SQLite and a local virtualenv are the default path,
and the Docker/Postgres setup in the repo is optional. There is no web interface, no API and no admin.

```bash
python manage.py migrate
python manage.py load_questionnaire banks/ipip-big-five-50.json

python manage.py add_target seed_username      # creates a target
python manage.py list_frameworks               # what is loaded
python manage.py run_target 1                  # runs one attempt in the foreground
python manage.py report_target 1               # prints the profile
```

`run_target` needs no worker: it runs the pipeline in this process. The queue is still there for batch
work, and it is the only path that retries:

```bash
python manage.py queue_scrape 1   # enqueue
python manage.py qcluster         # consume, in a second shell (or docker compose run --rm worker ...)
python manage.py list_targets     # see where everything stands
```

A target walks `PENDING -> QUEUED -> SCRAPING -> COMPLETED`; a failed run ends on `FAILED` with the
reason in `last_error`, and `python manage.py reset_target <target_id>` clears the attempt history
before another try. `report_target <id> --json --out path` writes the same payload it prints.

The database is local and disposable, so the schema ships as a single migration,
`core/migrations/0001_initial.py`. When the models change, delete that file, run
`python manage.py makemigrations core`, remove `db.sqlite3` and migrate again rather than stacking a
second migration; migrations become additive the day there is data worth keeping.
