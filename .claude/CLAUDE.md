# Startup Radar — Claude Context

Single-user Python tool that aggregates startup-funding signals from RSS, Hacker News, SEC EDGAR, and (optional) Gmail newsletters; filters by user criteria; serves a Streamlit dashboard with application tracking, warm-intro lookup, and AI-generated research briefs.

## Stack
- Python ≥3.10 (`pyproject.toml`); eventual target 3.11.
- Package manager: `uv` — `pyproject.toml` + `uv.lock` are the source of truth (Phase 2). Add deps via `uv add <pkg>`; never reintroduce `requirements.txt`.
- DB: SQLite, single file (`startup_radar.db`).
- Web: Streamlit (single-file `app.py`, ~1100 LOC; multi-page split in Phase 11).
- HTTP: shared `httpx.Client` via `startup_radar/http.py::get_client(cfg)` (Phase 13). `requests` is no longer a direct dep.
- Parsing: `feedparser`, `beautifulsoup4`.
- Configuration: `config.yaml` validated by pydantic `AppConfig` in `startup_radar/config/` (Phase 5).
- Secrets: `credentials.json`, `token.json`, `.env` — never commit, never read via shell.

## Repo layout
```
.
├── startup_radar/                           # the package (created Phase 3)
│   ├── cli.py                               # Typer CLI (Phase 4): run, serve, deepdive; `run --scheduled` is the cron entry
│   ├── models.py                            # @dataclass Startup, JobMatch
│   ├── filters.py                           # StartupFilter + JobFilter (moved from root in Phase 5)
│   ├── config/{schema,loader}.py            # pydantic AppConfig (Phase 5) — single source of truth for config.yaml
│   ├── parsing/{funding,normalize}.py       # AMOUNT_RE/STAGE_RE/COMPANY_*; normalize_company, dedup_key
│   ├── research/deepdive.py                 # AI research brief generator (moved from root in Phase 4)
│   ├── observability/logging.py             # structlog pipeline — configure_logging(json: bool) + get_logger(name) (Phase 11)
│   ├── sources/                             # Source ABC + per-source subclasses
│   │   ├── base.py                          # Source ABC: name, enabled_key, fetch(cfg, storage=None), healthcheck()
│   │   ├── registry.py                      # SOURCES: dict[str, Source]
│   │   ├── _retry.py                        # Phase 11 — 40-LOC retry helper wrapping network calls (3 attempts, 1/2/4 s backoff)
│   │   └── {rss,hackernews,sec_edgar,gmail}.py
│   ├── storage/                             # Phase 10 — `git mv database.py → storage/sqlite.py`
│   │   ├── base.py                          # Storage Protocol — 33 methods (reads, writes, dedup, tracker, connections)
│   │   ├── sqlite.py                        # SqliteStorage: one connection/process, WAL, writes in `with self._conn:`
│   │   ├── migrator.py                      # apply_pending() — PRAGMA user_version walker; alembic rejected (CRITIQUE_APPENDIX §4)
│   │   ├── __init__.py                      # load_storage(cfg) factory — single entry point
│   │   └── migrations/                      # 0001_initial.sql + 0002_runs_table.sql (Phase 11); idempotent via CREATE … IF NOT EXISTS
│   └── web/                                 # Streamlit dashboard (split Phase 9)
│       ├── app.py                           # ~80-line shell: page-config, config load, get_storage(), sidebar
│       ├── cache.py                         # @st.cache_resource get_storage() + @st.cache_data(ttl=60) read wrappers
│       ├── state.py                         # session-state + widget key constants (collision-asserted at import)
│       ├── lookup.py                        # DuckDuckGo company lookup (hoisted DDGS import)
│       ├── connections.py                   # LinkedIn CSV → tier-1/tier-2 helpers (storage injected; moved from repo root in Phase 9)
│       └── pages/{1_dashboard,2_companies,3_jobs,4_deepdive,5_tracker}.py
├── sinks/google_sheets.py
├── scheduling/                              # cron, launchd, Windows Task templates
├── backups/                                 # local tarballs from `startup-radar backup` (gitignored, Phase 6)
├── tests/unit/test_web_smoke.py             # Phase 9 — AppTest shell smoke + page discovery + state collision
├── tests/unit/{test_cli_backup,test_cli_doctor,test_cli_status}.py  # Phase 6 — resilience CLI tests
├── tests/integration/                       # Phase 8 — vcrpy cassette-backed per-source tests
├── docs/                                    # PRODUCTION_REFACTOR_PLAN, CRITIQUE_APPENDIX, AUDIT_FINDINGS, plans/phase-N
└── .claude/                                 # this directory — harness
```
Target layout (Phase 10+) lives in `docs/PRODUCTION_REFACTOR_PLAN.md` §3.1.

## Core invariants
- **Must:** every outbound HTTP call goes through `startup_radar.http.get_client(cfg)` — the process-wide `httpx.Client` whose default timeout is `cfg.network.timeout_seconds` and whose default `User-Agent` is `startup-radar/<version>`. No bare `httpx.get` / `requests.*` anywhere under `startup_radar/` (the lone exception is `sources/gmail.py`'s `google.auth.transport.requests.Request`, which is google-auth's internal transport, not our `requests` use).
- **Must:** every source subclasses `startup_radar.sources.base.Source`, sets `name` + `enabled_key`, and implements `fetch(cfg, storage=None) -> list[Startup]`. Free-function `fetch(...)` is gone since Phase 3. `storage` is only consumed by sources that dedup (today: `gmail.py` via `is_processed` / `mark_processed`).
- **Must:** every source registers in `startup_radar/sources/registry.py`.
- **Must:** funding regexes (`AMOUNT_RE`, `STAGE_RE`, `COMPANY_SUBJECT_RE`, `COMPANY_INLINE_RE`) live ONLY in `startup_radar/parsing/funding.py`. Never re-introduce duplicates per source.
- **Must:** company-name normalization goes through `normalize_company` / `dedup_key` in `startup_radar/parsing/normalize.py`.
- **Never:** `print()` outside `startup_radar/cli.py`, `startup_radar/research/deepdive.py`, or `tests/` — use `from startup_radar.observability.logging import get_logger; log = get_logger(__name__)`.
- **Never:** `os.getenv()` outside `startup_radar/config/` — `startup_radar/config/secrets.py` exposes the cached `Secrets(BaseSettings)` instance via `secrets()`; all env-var reads go through it.
- **Never:** edit `credentials.json`, `token.json`, `.env`, `uv.lock`, or `*.db` files.
- **Never:** reintroduce `requirements.txt` — `pyproject.toml` + `uv.lock` are authoritative since Phase 2.
- **Never:** add Postgres, alembic, async pipeline, or dashboard auth — out of scope per `docs/CRITIQUE_APPENDIX.md` §12.

## Common commands
```bash
make lint                        # ruff check
make format                      # ruff format (writes)
make format-check                # ruff format --check (no writes)
make test                        # pytest
make typecheck                   # mypy
make ci                          # lint + format-check + typecheck + test
make serve                       # uv run startup-radar serve
make run                         # uv run startup-radar run
uv run startup-radar run --scheduled      # cron/launchd mode (logs + 15-min timeout)
uv run startup-radar deepdive "Anthropic" # research brief .docx
uv run startup-radar status               # branch + version + last-run age + DB row counts
uv run startup-radar doctor [--network]   # env / config / credentials / source healthchecks
uv run startup-radar backup [--no-secrets] [--db-only] # local tar.gz of DB + config + OAuth
```

## Gotchas
- `data` branch (GH Actions DB store, Phase 7) — NEVER delete, rebase, or force-push from a developer machine. The daily workflow writes to it; the weekly GC workflow is the only sanctioned force-pusher. To pull the prod DB locally: `git fetch origin data:data && git checkout data -- startup_radar.db`.
- `feedparser` has no HTTP of its own anymore — Phase 13 flipped `sources/rss.py` to fetch via `get_client(cfg).get(url)` then `feedparser.parse(r.content)`. The old `socket.setdefaulttimeout(20)` hack is gone; timeout is inherited from the shared client.
- Shared `httpx.Client` is process-cached by `get_client(cfg)` (keyed on `cfg.network.timeout_seconds`). Tests call `get_client.cache_clear()` via an autouse fixture in `tests/conftest.py` alongside `secrets.cache_clear()`. To stub the client in tests, monkeypatch `startup_radar.sources.<name>.get_client` to return a fake client.
- SEC EDGAR requires `User-Agent: Name email@example.com` header AND ≤10 req/s.
- Streamlit re-runs the entire script on every interaction — wrap DB reads in `@st.cache_data(ttl=60)` via `startup_radar/web/cache.py`. Writes invalidate immediately by calling `load_data.clear()` after the insert.
- Dashboard sidebar (Run-pipeline button + LinkedIn uploader) lives ONLY in `startup_radar/web/app.py` (the shell). Native multi-page runs the shell on every page render, so sidebar code in the shell appears on every page — do NOT duplicate into pages.
- Session-state / widget keys in `startup_radar/web/pages/*` go through `startup_radar/web/state.py` constants. `state.assert_no_collisions()` fires at import time; two constants pointing at the same string raise `AssertionError` before Streamlit loads.
- GH Actions DB persistence uses commit-to-`data`-branch (Phase 7) — see `docs/ops/data-branch.md`. The old `actions/cache`-keyed-by-`run_id` scheme is gone.
- OAuth scopes for Gmail (`gmail.readonly`) and Sheets (`spreadsheets`) are merged into a single `token.json` — Phase 0 fix.
- Dedup key strips legal suffixes (`inc`, `llc`, `corp`, `gmbh`, `labs`, etc.) — see `LEGAL_SUFFIX_RE` in `startup_radar/parsing/normalize.py`. Real failure mode is "OpenAI" vs "Open AI Inc.", not whitespace.
- `parse_amount_musd("$2.5M") -> 2.5` from `startup_radar/parsing/funding.py` is the canonical amount parser — `startup_radar/filters.py` uses it (the duplicate `_parse_amount_musd` retired in Phase 5).
- CLI entry-point is registered via `[project.scripts]` in `pyproject.toml` and the `startup_radar.cli:app` shim — `uv sync --all-extras` refreshes it after edits to `cli.py` are not needed (editable install), but adding/removing commands does require a re-sync to refresh the `startup-radar` script wrapper.
- Version is derived by `setuptools-scm` from the git tag history (`phase-*` tags yield dev-style versions; `fallback_version = "0.1.0"` for source tarballs).
- vcrpy cassettes live in `tests/fixtures/cassettes/<source>/`. `CI=1` sets `record_mode=none` (missing cassette → test fails loud). Locally `record_mode=once` records on first run. Re-record by deleting the yaml + rerunning the test. EDGAR cassettes scrub User-Agent to `startup-radar-test`; don't commit a real email.
- `SqliteStorage` holds **one** `sqlite3.Connection` for its lifetime (Phase 10). `check_same_thread=False` is required so Streamlit's thread pool can share reads; single-writer is still enforced because only the CLI pipeline or a user-triggered button writes. Never call `sqlite3.connect()` directly — go through `load_storage(cfg)` (CLI/tests) or `get_storage()` (dashboard, cached via `@st.cache_resource`). Every write wraps `with self._conn:` for atomic commit-or-rollback.
- Schema changes = drop `NNNN_<slug>.sql` into `startup_radar/storage/migrations/` with the next integer prefix (migrator rejects gaps and bad filenames at load time). No down-migrations, no alembic — rollback is git-revert + restore from the backup tarball. Next `startup-radar run` (or `make db-migrate`) applies it.
- Logging is structlog with the stdlib bridge (Phase 11). `configure_logging(json: bool)` is called exactly once — at CLI `@app.callback` and inside the dashboard shell. `CI=1` or `STARTUP_RADAR_LOG_JSON=1` flip it to JSON; locally it's a pretty `ConsoleRenderer`. In tests, `tests/conftest.py` autouse-configures it so `caplog.records` sees source warnings. Don't call `logging.basicConfig` anywhere; don't wipe root handlers — our handler is sentinel-tagged and swaps in place so pytest's `LogCaptureHandler` survives.
- Source network calls go through `startup_radar.sources._retry.retry(fn, on=(...), context={...})` — three attempts, `(1, 2, 4)` s backoff, logs `retry.backoff` at WARNING on each. Sleep is `_retry._sleep` (a module-local alias of `time.sleep`); `conftest.py` autouse-monkeypatches that alias to a no-op so failure-path tests don't cost 7 s each. Do NOT monkeypatch `time.sleep` — it's a module reference and clobbering `.sleep` on it freezes Streamlit's AppTest poll loop.
- Pipeline wraps each source in `try/except/finally` → `storage.record_run(key, started_at=..., ended_at=..., items_fetched=..., items_kept=..., error=..., user_version_at_run=...)`. `status` renders a `Per-source health:` block using `storage.last_run` + `storage.failure_streak`. `doctor` adds a `⚠ source.<key>.streak` row when failure_streak > 2 (does NOT increment failed checks — advisory only).
- Env vars go through `from startup_radar.config import secrets; secrets().log_json` (Phase 12). `Secrets` uses `env_prefix="STARTUP_RADAR_"`; `CI` and `SENTRY_DSN` are unprefixed aliases. `.env` is gitignored; `.env.example` documents the knobs. The module-level `secrets()` is `lru_cache`'d; `tests/conftest.py` autouse-clears it so `monkeypatch.setenv` doesn't leak.

## @import references
For source-author conventions: @.claude/rules/sources.md
For storage/DB conventions: @.claude/rules/storage.md
For Streamlit conventions: @.claude/rules/dashboard.md
For logging/observability: @.claude/rules/observability.md
For test conventions: @.claude/rules/testing.md
For overall refactor plan: @docs/PRODUCTION_REFACTOR_PLAN.md
For critique/calibration: @docs/CRITIQUE_APPENDIX.md
For Phase 1 plan (this harness): @docs/plans/phase-1.md

## Subagents
- `source-implementer` — scaffold a new data source under `startup_radar/sources/` (Source subclass + registry entry).
- `filter-tuner` — diagnose `filters.py` precision/recall against fixtures (read-only).
- `dashboard-page` — scaffold a new Streamlit page.

## Do NOT delegate
- Anything touching secrets, OAuth flows, or `config.yaml` writes — hand back to user.
- Commits and pushes — surface diff, let the user run `git commit`. Two sanctioned exceptions: the `/ship` skill (commit only) and the `/data-branch-bootstrap` skill (one-shot push of the orphan `data` branch). Both gated by env-var handshakes the `pre-bash.sh` hook checks (`STARTUP_RADAR_SHIP=1` and `STARTUP_RADAR_DATA_BOOTSTRAP=1`).
