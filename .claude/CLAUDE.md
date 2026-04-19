# Startup Radar — Claude Context

Single-user Python tool that aggregates startup-funding signals from RSS, Hacker News, SEC EDGAR, and (optional) Gmail newsletters; filters by user criteria; serves a Streamlit dashboard with application tracking, warm-intro lookup, and AI-generated research briefs.

## Stack
- Python ≥3.10 (`pyproject.toml`); eventual target 3.11.
- Package manager: `uv` — `pyproject.toml` + `uv.lock` are the source of truth (Phase 2). Add deps via `uv add <pkg>`; never reintroduce `requirements.txt`.
- DB: SQLite, single file (`startup_radar.db`).
- Web: Streamlit (single-file `app.py`, ~1100 LOC; multi-page split in Phase 11).
- HTTP: `requests` today; migrating to `httpx` in Phase 13.
- Parsing: `feedparser`, `beautifulsoup4`.
- Configuration: `config.yaml` validated by `config_loader.py`; pydantic schema lands Phase 7.
- Secrets: `credentials.json`, `token.json`, `.env` — never commit, never read via shell.

## Repo layout
```
.
├── main.py                                  # pipeline entry — Typer CLI lands Phase 4
├── daily_run.py                             # cron wrapper with logging + 15-min timeout
├── app.py                                   # Streamlit dashboard (5 pages, single file; split Phase 11)
├── deepdive.py                              # AI research brief generator (moves to startup_radar/research/ Phase 4)
├── database.py                              # SQLite layer (33 fns; moves to startup_radar/storage/ Phase 12)
├── filters.py                               # StartupFilter + JobFilter (moves Phase 5)
├── config_loader.py                         # YAML loader (pydantic schema replaces it Phase 5)
├── connections.py                           # LinkedIn CSV → tier-1/tier-2 (moves Phase 11)
├── startup_radar/                           # the package (created Phase 3)
│   ├── models.py                            # @dataclass Startup, JobMatch
│   ├── parsing/{funding,normalize}.py       # AMOUNT_RE/STAGE_RE/COMPANY_*; normalize_company, dedup_key
│   └── sources/                             # Source ABC + per-source subclasses
│       ├── base.py                          # Source ABC: name, enabled_key, fetch(cfg), healthcheck()
│       ├── registry.py                      # SOURCES: dict[str, Source]
│       └── {rss,hackernews,sec_edgar,gmail}.py
├── sinks/google_sheets.py
├── scheduling/                              # cron, launchd, Windows Task templates
├── tests/test_smoke.py                      # Phase 0 placeholder; real coverage Phase 10
├── tests/parsing/{test_funding,test_normalize}.py  # Phase 3
├── docs/                                    # PRODUCTION_REFACTOR_PLAN, CRITIQUE_APPENDIX, AUDIT_FINDINGS, plans/phase-N
└── .claude/                                 # this directory — harness
```
Target layout (Phase 11+) lives in `docs/PRODUCTION_REFACTOR_PLAN.md` §3.1.

## Core invariants
- **Must:** every new HTTP call uses `timeout=` (or shared `httpx.Client` once it lands). `feedparser` is the exception — see `startup_radar/sources/rss.py` (sets `socket.setdefaulttimeout(20)` at module load).
- **Must:** every source subclasses `startup_radar.sources.base.Source`, sets `name` + `enabled_key`, and implements `fetch(cfg) -> list[Startup]`. Free-function `fetch(...)` is gone since Phase 3.
- **Must:** every source registers in `startup_radar/sources/registry.py`.
- **Must:** funding regexes (`AMOUNT_RE`, `STAGE_RE`, `COMPANY_SUBJECT_RE`, `COMPANY_INLINE_RE`) live ONLY in `startup_radar/parsing/funding.py`. Never re-introduce duplicates per source.
- **Must:** company-name normalization goes through `normalize_company` / `dedup_key` in `startup_radar/parsing/normalize.py`.
- **Never:** `print()` outside `main.py`, `daily_run.py`, `deepdive.py`, or `tests/` — use `logging.getLogger(__name__)`.
- **Never:** `os.getenv()` outside `config_loader.py` (later: `startup_radar/config/`).
- **Never:** edit `credentials.json`, `token.json`, `.env`, `uv.lock`, or `*.db` files.
- **Never:** reintroduce `requirements.txt` — `pyproject.toml` + `uv.lock` are authoritative since Phase 2.
- **Never:** add Postgres, alembic, async pipeline, or dashboard auth — out of scope per `docs/CRITIQUE_APPENDIX.md` §12.

## Common commands
```bash
make lint           # ruff check
make format         # ruff format (writes)
make format-check   # ruff format --check (no writes)
make test           # pytest
make typecheck      # mypy
make ci             # lint + format-check + typecheck + test
make serve          # streamlit run app.py
make run            # python main.py
```

## Gotchas
- `feedparser` does NOT take a `timeout` kwarg — `startup_radar/sources/rss.py` uses `socket.setdefaulttimeout(20)` at module load.
- SEC EDGAR requires `User-Agent: Name email@example.com` header AND ≤10 req/s.
- Streamlit re-runs the entire script on every interaction — wrap DB reads in `@st.cache_data(ttl=60)` (already done at `app.py:59`).
- GH Actions cache for the SQLite DB is unsound (`docs/CRITIQUE_APPENDIX.md` §1, item 1) — Phase 9 replaces it with commit-to-data-branch.
- OAuth scopes for Gmail (`gmail.readonly`) and Sheets (`spreadsheets`) are merged into a single `token.json` — Phase 0 fix.
- Dedup key strips legal suffixes (`inc`, `llc`, `corp`, `gmbh`, `labs`, etc.) — see `LEGAL_SUFFIX_RE` in `startup_radar/parsing/normalize.py`. Real failure mode is "OpenAI" vs "Open AI Inc.", not whitespace.
- `parse_amount_musd("$2.5M") -> 2.5` lives in `startup_radar/parsing/funding.py` but is NOT yet wired into `filters.py` (which keeps its own copy until Phase 5).

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
- Commits and pushes — surface diff, let the user run `git commit`.
