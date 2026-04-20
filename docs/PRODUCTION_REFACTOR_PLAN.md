# Startup Radar — Production Refactor Plan

> Goal: turn this repo from a "works on my machine" template into a production-grade Python application with one-command DX, real testing, observability, and a robust Claude Code coding harness.

> **v1.1 — Calibrated.** This plan was reviewed by an independent senior-engineer audit ([CRITIQUE_APPENDIX.md](./CRITIQUE_APPENDIX.md)). Section §0a below supersedes anything below it that conflicts. Original sections kept intact for reasoning trail.

---

## 0a. Calibration overrides (read first)

This is a **single-user personal tool** that wants production-grade DX, not a SaaS. The audit downgraded several items as overkill. Apply these overrides to everything below:

### Drops (don't do)
| Item | Why dropped |
|---|---|
| Postgres in docker-compose (§3.5, §0) | No second user. Single-user SQLite is fine. |
| Alembic (§3.5) | 50-line homegrown migrator using `PRAGMA user_version` + numbered `.sql` files suffices. |
| SQLAlchemy Core (§3.5) | 33 functions of straight SQL; abstraction tax > benefit. |
| Async pipeline (§4.6) | 4 sources, 1 min/day. Use `ThreadPoolExecutor(4)` if anything; or skip. |
| Dashboard auth (§5) | localhost-only personal tool. |
| PyPI release pipeline (§5) | `pipx install git+https://github.com/...` works fine, no PyPI needed. |
| `migration-author` subagent (§6.5) | No alembic. |
| Postgres-related items in compose | See above. |
| Docker compose `dev` flow as primary | `uv run startup-radar serve` IS the dev workflow. Compose only if someone else ever runs this. |

### Demotes (do later, not now)
- **Async pipeline** → Tier 4 nice-to-have
- **Circuit breaker** → per-source failure flag is enough
- **`playwright` MCP** → defer until multi-page Streamlit work warrants it
- **Streamlit `components/` dir** → wait until ≥3 reuses; premature DRY in Streamlit creates rerun-state bugs

### Adds (missing from v1.0)
| Item | Tier | Why |
|---|---|---|
| ✅ `startup-radar backup` → tarball of DB + config + token | Tier 1 | **DONE Phase 6** — writes `backups/startup-radar-<ts>.tar.gz` with DB + `config.yaml` + OAuth; `--no-secrets`/`--db-only` flags. `backups/` gitignored. Tag: `phase-6`. |
| `startup-radar export --format csv\|json` | Tier 2 | User owns their data. |
| `PRAGMA user_version` schema versioning | Tier 2 | Even without alembic. |
| `setuptools-scm` git-tag versioning in `pyproject.toml` | Tier 1 | Move from Tier 4 to Tier 1 alongside `pyproject.toml` work. |
| Gmail token auto-refresh on expiry | Tier 3 | `daily_run.py:88-90` only detects and tells user to re-auth manually. Personal unattended cron should automate. |
| Fix `threading.Timer` race in `daily_run.py:70` | Tier 0 | Low probability but real. |
| `mypy --strict` posture decision (commit or defer) | Tier 1 | One-line stance in `pyproject.toml`. |
| Robots.txt / ToS posture note for scraped sources | Tier 4 | One-liner in docs. |
| Explicit "no telemetry" statement | Tier 4 | Pre-empt the question. |

### Corrections to bug list
- **Tier 0 #1 wording:** GH Actions DB persistence is **unsound**, not "broken." `restore-keys: startup-radar-db-` does match the most recent prefix-keyed entry, so persistence usually works. Real bugs: (a) writes non-deterministic under concurrent runs, (b) GH evicts caches after 7 days no-access, (c) PR runs can poison main's data via branch fallback.
- **Tier 0 #4 dedup example wrong:** `re.sub(r"[\s.\-]+", "")` *does* collapse "We Work" → "wework". Real failure: **"OpenAI" vs "Open AI Inc."** (suffixes, capitalization variants). Fix the canonical form to also strip legal suffixes (`inc`, `llc`, `corp`).
- **Tier 0 #6 timeout caveat:** `feedparser` (used in `sources/rss.py`) doesn't take a `timeout` kwarg. Either `socket.setdefaulttimeout()` or switch RSS to `httpx`+`feedparser.parse(string)`.
- **DB connection-per-call framing:** for single-user SQLite, this is **not a perf issue** (open is microseconds). Refactor reason is testability + transactional grouping, not performance.

### CLI surface revisions (§2.1)
- Drop `db` as a top-level verb; use `startup-radar admin <op>` for migrate/reset/export.
- Add `startup-radar status` (last-run age, source health) and `startup-radar logs --tail`.
- Make sure `schedule install` actually replaces `scheduling/*` rather than living alongside.

### Claude harness revisions (§6)
- **Don't run `make ci` on `Stop` hook.** ruff+mypy+pytest is 30-60s; firing on every Stop event when you asked for a one-line clarification is friction within a week. Run **lint+format only** on `Stop`. Gate full CI behind a `/ship` skill invocation. Or scope `Stop` matcher to fire only when files were edited that session.
- **`post-edit.sh` should be sync, not async.** Async means Claude moves on before format completes — can race the next edit. Sync but only on the changed file.
- Add `Edit(uv.lock)` deny — regenerate via `uv lock`, not manual edit.
- Don't publish to PyPI — use `pipx install git+https://github.com/...`.

### Lockfile hygiene (§2.2)
Don't commit `uv.lock` AND a `requirements.txt`. Pick `uv.lock` as source of truth; generate `requirements.txt` via `uv export` if GH Actions needs it.

### Re-ordered execution (replaces §7)
| Order | Item | Effort | Notes |
|---|---|---|---|
| 1 | Streamlit `@st.cache_data(ttl=60)` on `load_data()` | 30 min | Tier 0 perf bug. |
| 2 | CI scaffolding: ruff + mypy + empty pytest job | 0.5 day | Without tests, all subsequent refactors are risky. Fixtures come later. |
| 3 | `.claude/` harness: settings.json + sane hooks + subagents | 0.5 day | Lets you safely do everything below. |
| 4 | `pyproject.toml` + `uv` + `setuptools-scm` + entry-point | 1 day | DX foundation. |
| 5 | ✅ Source ABC + centralized parsing module + registry | 0.5 day | **DONE Phase 3** — `startup_radar/sources/{base,registry}.py` + `parsing/{funding,normalize}.py`. Tag: `phase-3`. |
| 6 | ✅ Typer CLI + research/ subpackage + scm versioning | 1 day | **DONE Phase 4** — `startup-radar run|serve|deepdive`; `run --scheduled` folds the old `daily_run.py` logging+timeout; `deepdive.py` relocated to `startup_radar/research/`; `[project.scripts]` + `setuptools-scm` wired. Tag: `phase-4`. |
| 7 | ✅ Pydantic config + filters move | 0.5 day | **DONE Phase 5** — `startup_radar/config/{schema,loader}.py` (pydantic `AppConfig`, `extra="forbid"`, field-path error messages); `filters.py` → `startup_radar/filters.py` typed against `AppConfig`; `parse_amount_musd` wired in (retired duplicate `_parse_amount_musd`); `Source.fetch(cfg: AppConfig)` retyped and all 4 sources + `cli.py` + `deepdive.py` + `app.py` updated. `.env` / `pydantic-settings` deferred to Phase 13 (no current env-var consumer). Tag: `phase-5`. |
| 8 | ✅ `startup-radar backup` + `doctor` + `status` | 0.5 day | **DONE Phase 6** — three Typer commands; `Source.healthcheck()` extended to `(cfg, *, network=False) -> tuple[bool, str]` with per-source overrides; `backups/` gitignored; 11 new CLI tests. Tag: `phase-6`. |
| 9 | ✅ GH Actions DB persistence via commit-to-data-branch | 1 day | **DONE Phase 7** — `daily.yml` rewrite + `data-branch-gc.yml` weekly force-push + `docs/ops/data-branch.md` bootstrap. Tag: `phase-7`. |
| 10 | ✅ vcrpy fixtures + real source tests | 3-4 days | **DONE Phase 8** — `tests/unit/` + `tests/integration/` split; per-source cassette-backed tests (happy/empty/failure) for `rss`/`hackernews`/`sec_edgar`; Gmail via stubbed `service_factory`; `.github/workflows/ci.yml` PR gate (ruff + format-check + mypy + pytest w/ `--cov`); coverage config in `pyproject.toml`; `make test-unit|test-integration|test-record`. Tag: pending `phase-8`. |
| 11 | ✅ Decompose `app.py` into `web/pages/` + cache wrappers | 2 days | **DONE Phase 9** — `startup_radar/web/{app,cache,state,lookup,connections}.py` + `pages/{1_dashboard,2_companies,3_jobs,4_deepdive,5_tracker}.py`; `@st.cache_data(ttl=60)` wrappers centralized in `web/cache.py`; session-state keys hoisted to `web/state.py` with import-time collision assertion; dead `from main import run` button replaced with promoted `startup_radar.cli.pipeline`; `startup-radar serve` repointed; `streamlit.testing.v1.AppTest` shell smoke test. `web/components/` deliberately skipped. Tag: pending `phase-9`. |
| 12 | ✅ Storage class + `PRAGMA user_version` migrator (NOT alembic) | 1 day | **DONE Phase 10** — `database.py` retired via `git mv` → `startup_radar/storage/sqlite.py`; `SqliteStorage` single-connection class (WAL, `check_same_thread=False`, writes in `with self._conn:`); homegrown `apply_pending` migrator over `NNNN_<slug>.sql` files with strict-ascending filename validation; `0001_initial.sql` is idempotent over pre-Phase-10 DBs (every `CREATE … IF NOT EXISTS`); `Storage` Protocol in `storage/base.py` + `load_storage(cfg)` factory; `Source.fetch` signature now `(cfg, storage=None)` — only `gmail.py` reads storage for dedup; `@st.cache_resource` wraps `get_storage()` in `web/cache.py`; 11 new tests (7 migrator + 4 SqliteStorage smoke). Alembic explicitly rejected per `CRITIQUE_APPENDIX.md` §4. Tag: pending `phase-10`. |
| 13 | ✅ structlog + retries + per-source failure counters | 1 day | **DONE Phase 11** — `startup_radar/observability/logging.py` (stdlib-bridged structlog, idempotent, sentinel-tagged handler keeps pytest's `caplog` attached); `startup_radar/sources/_retry.py` (~40 LOC, `(1,2,4) s` backoff, no `tenacity`/`backoff`); `0002_runs_table.sql` + `record_run` / `last_run` / `failure_streak`; `pipeline()` try/except/finally wraps each source with `record_run`; `status` renders `Per-source health:`; `doctor` surfaces `⚠ source.<key>.streak` when `failure_streak > 2` (advisory, exit stays driven by checks); `cfg.network.timeout_seconds=10` added. All `extra={}` kwargs flattened. Tag: pending `phase-11`. |
| 14 | ✅ `pydantic-settings` + `.env` secrets loader | 0.5 day | **DONE Phase 12** — `startup_radar/config/secrets.py` exposes `Secrets(BaseSettings)` + lru-cached `secrets()`; `env_prefix="STARTUP_RADAR_"` with `CI` / `SENTRY_DSN` unprefixed aliases; `extra="ignore"` tolerates shell-only vars (`STARTUP_RADAR_SHIP`, etc.). Retired the two surviving `os.getenv` sites in `cli.py:28` + `web/app.py:22`. `.env.example` committed; `tests/conftest.py` autouse-clears the cache between tests. `SENTRY_DSN` field defined but Sentry SDK wiring dropped from the plan (single-user tool — structlog + `runs` + `doctor` cover it). Tag: pending `phase-12`. |
| 15 | ✅ `httpx.Client` migration + shared HTTP surface | 0.5 day | **DONE Phase 13** — `startup_radar/http.py` exposes `get_client(cfg) -> httpx.Client` (lru-cached per process; `timeout=cfg.network.timeout_seconds`; default `User-Agent: startup-radar/<version>`; `follow_redirects=True`). All three sources (`rss`, `hackernews`, `sec_edgar`) route through it; `sources/rss.py` now fetches bytes via the client and calls `feedparser.parse(r.content)`, retiring the `socket.setdefaulttimeout(20)` module-load hack. Retry tuples updated from `requests.RequestException` → `httpx.HTTPError`. `requests` removed from direct deps (stays transitively via `[google]` extra). `tests/conftest.py` autouse-clears the client cache. Tier 0 #6 closed. Tag: pending `phase-13`. |
| 16 | Dockerfile (single image, optional) | 0.5 day | |
| 17 | MkDocs site (optional) | 1 day | |

**Realistic total: 15-18 engineering days** (v1.0 said 10-13; underestimated by ~40%). Items 1-9 (~6 days) deliver 80% of the value.

---

## 0. North star DX

```bash
# Install
pipx install startup-radar               # or: uv tool install startup-radar

# One-time setup
startup-radar init                       # interactive wizard → config + .env
startup-radar doctor                     # validates environment, exit 0/1

# Daily use
startup-radar run                        # pipeline once
startup-radar serve                      # dashboard at :8501
startup-radar deepdive Anthropic         # research brief
startup-radar schedule install --gh      # provisions GitHub Action

# Contributors
make dev                                 # docker compose up + hot-reload
make test                                # ruff + mypy + pytest
make ci                                  # full pipeline locally
```

One CLI. One config path. One DB. Everything else is a `--flag`.

---

## 1. Tier 0 — Bugs to fix first

| # | Bug | Location | Fix |
|---|---|---|---|
| 1 | ✅ **FIXED (Phase 7)** GH Actions DB persistence via commit-to-`data`-branch + weekly orphan GC. See `docs/ops/data-branch.md`. |
| 2 | **OAuth scope split** between Gmail (`gmail.readonly`) and Sheets (`spreadsheets`) — same `token.json` can't serve both | `sources/gmail.py:30`, `sinks/google_sheets.py:13` | Single OAuth client, merged scope list, single `token.json` |
| 3 | **Silent source failures** — exceptions swallowed to `print()`; dead feed reports 0 candidates indistinguishably from a slow news day | `sources/rss.py:94`, `hackernews.py:45`, `sec_edgar.py:49` | Structured logging w/ severity + per-source success counters surfaced in dashboard |
| 4 | **Naive dedup** — collapses spaces/dashes only ("WeWork" ≠ "We Work") | `main.py:21` | Normalized-name + canonical domain key in DB; index it |
| 5 | **Streamlit re-queries entire DB on every keystroke** — no caching | `app.py:58 load_data()` | `@st.cache_data(ttl=60)` — single biggest perf win, 30 minutes of work |
| 6 | ✅ **FIXED (Phase 13)** Shared `httpx.Client` via `startup_radar/http.py::get_client(cfg)`; default timeout = `cfg.network.timeout_seconds`; `requests` removed from direct deps. |

---

## 2. Tier 1 — DX: collapse the command shitshow

### 2.1 One CLI via Typer
Replace `main.py` + `daily_run.py` + the `streamlit run app.py` / `/deepdive` incantations with a single `cli.py`:

```python
# startup_radar/cli.py
import typer
app = typer.Typer(rich_markup_mode="rich")

@app.command() def init():       """Interactive setup wizard."""
@app.command() def run(once: bool = True, sources: list[str] = None):
    """Run the discovery pipeline."""
@app.command() def serve(port: int = 8501, reload: bool = False):
    """Open the Streamlit dashboard."""
@app.command() def deepdive(company: str, output: Path = None):
    """Generate a research brief for a company."""
@app.command() def schedule(action: str = typer.Argument(..., help="install|remove|status")):
    """Manage scheduled runs (cron/launchd/GH Actions)."""
@app.command() def doctor():
    """Diagnose configuration, credentials, network, DB."""
@app.command() def db(action: str):
    """DB ops: migrate | reset | export | import."""
```

Console-script entry in `pyproject.toml`:
```toml
[project.scripts]
startup-radar = "startup_radar.cli:app"
```

Kills all three current entry points (`main.py`, `daily_run.py`, `streamlit run app.py`).

### 2.2 `pyproject.toml` + `uv` (replaces `requirements.txt`)
```toml
[project]
name = "startup-radar"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["feedparser>=6.0", "httpx>=0.27", "pydantic>=2.5", "typer>=0.12", ...]

[project.optional-dependencies]
gmail = ["google-api-python-client", "google-auth-oauthlib"]
sheets = ["gspread"]
dashboard = ["streamlit>=1.30", "plotly"]
all = ["startup-radar[gmail,sheets,dashboard]"]

[tool.uv]
dev-dependencies = ["pytest", "pytest-cov", "ruff", "mypy", "vcrpy"]
```

`uv sync --all-extras` replaces `pip install -r requirements.txt`. Lockfile (`uv.lock`) gets committed. Optional deps no longer crash at runtime if missing.

### 2.3 `Makefile` for contributor commands
```make
.PHONY: install dev test lint typecheck ci serve seed clean

install:    ; uv sync --all-extras
dev:        ; docker compose up --build
test:       ; uv run pytest -xvs --cov=startup_radar
lint:       ; uv run ruff check . && uv run ruff format --check .
typecheck:  ; uv run mypy startup_radar
ci:         lint typecheck test
serve:      ; uv run startup-radar serve --reload
seed:       ; uv run startup-radar run --sources rss --limit 10
clean:      ; rm -rf .pytest_cache .mypy_cache dist build *.egg-info
```

### 2.4 Dockerfile + `docker compose up`
- `Dockerfile` (multi-stage, ~80MB final via `python:3.11-slim`)
- `docker-compose.yml` with `radar` (CLI/dashboard) + `postgres` (optional storage upgrade) services
- `.devcontainer/devcontainer.json` for one-click VS Code setup

### 2.5 `startup-radar doctor`
Validates: Python ≥3.11, `config.yaml` exists & schema-valid, DB writable, credentials present for enabled sources, network to each enabled feed, sufficient disk for reports/. Exit 0/1 — usable in CI and as the first step of `serve`/`run`.

---

## 3. Tier 2 — Architecture restructuring

### 3.1 Proper package layout
```
startup_radar/
  __init__.py
  cli.py                    # Typer app
  config/
    schema.py               # pydantic models, replaces config_loader.py
    loader.py
    secrets.py              # pydantic-settings from .env
  sources/
    base.py                 # Source ABC: name, fetch(), healthcheck()
    rss.py
    hackernews.py
    sec_edgar.py
    gmail.py
    registry.py             # SOURCES: dict[str, Source]
  parsing/
    funding.py              # _AMOUNT_RE, _STAGE_RE — currently dup'd 4x
    normalize.py            # company-name canonical form
    dates.py
  filters.py
  storage/                  # ✅ DONE Phase 10 — `git mv database.py → storage/sqlite.py`
    base.py                 # Storage Protocol
    sqlite.py               # SqliteStorage (single connection, WAL, writes in `with self._conn:`)
    migrator.py             # homegrown `apply_pending` over PRAGMA user_version; alembic rejected per CRITIQUE_APPENDIX §4
    migrations/             # NNNN_<slug>.sql — 0001_initial.sql is the baseline
  sinks/
    sheets.py
    notion.py               # future
  research/
    deepdive.py
    scoring.py
    web_search.py
  web/
    app.py                  # Streamlit shell (~50 lines)
    pages/
      1_dashboard.py
      2_companies.py
      3_jobs.py
      4_deepdive.py
      5_tracker.py
    components/             # reusable widgets
    cache.py                # @st.cache_data wrappers
    state.py                # session-state keys as constants
  scheduling/
    github_actions.py       # generates workflow YAML
    cron.py
    launchd.py
    windows.py
  observability/
    logging.py              # structlog setup
    metrics.py              # per-source counters
    sentry.py               # gated by SENTRY_DSN
tests/
  unit/
  integration/
  fixtures/                 # vcrpy cassettes
  conftest.py
.claude/                    # see Section 6
docs/
  ARCHITECTURE.md
  CONTRIBUTING.md
  sources/adding-a-source.md
.github/workflows/
  ci.yml                    # PR validation
  daily.yml                 # cron pipeline
  release.yml               # tag → PyPI
pyproject.toml
uv.lock
Dockerfile
docker-compose.yml
.devcontainer/devcontainer.json
.env.example
Makefile
```

### 3.2 `Source` ABC kills duplication
```python
# startup_radar/sources/base.py
class Source(ABC):
    name: str
    enabled_key: str   # config path

    @abstractmethod
    def fetch(self, cfg) -> list[Startup]: ...
    def healthcheck(self) -> bool: return True
```

`main.py:60-95` becomes a 5-line loop over `SOURCES`. Adding a source = one file + one registry line.

### 3.3 Pydantic config + `.env` for secrets
**Schema portion DONE — Phase 5.** `startup_radar/config/schema.py` (pydantic `AppConfig`) replaces `config_loader.py`'s 4-key existence check:
- Validation errors point at field paths (e.g. `targets.min_stage: Input should be 'pre-seed', 'seed', ...`)
- `extra="forbid"` catches YAML typos
- IDE autocomplete on `cfg.targets.min_stage`
- `startup_radar/config/loader.py::load_config()` is the one entry point, returning `AppConfig`

✅ **DONE Phase 12.** `startup_radar/config/secrets.py` exposes `Secrets(BaseSettings)` with `env_prefix="STARTUP_RADAR_"` (plus unprefixed `CI` / `SENTRY_DSN` aliases) and a lru-cached `secrets()` accessor — the single entry point for every env-var read under `startup_radar/`. `.env.example` committed; `.env` stays gitignored. `SENTRY_DSN` is a defined field but no SDK wiring exists yet — Sentry integration is the next phase's first task.

### 3.4 Dashboard decomposition
`app.py` is 1,104 lines and re-runs everything on every click. Move each page into `web/pages/N_name.py` (Streamlit native multi-page). Extract:
- `web/cache.py` — `@st.cache_data(ttl=60)` on all DB reads
- `web/components/` — company card, status pill, intro list (currently inline 3-4×)
- `web/state.py` — kills the `key="ap_company"` collisions noted at `app.py:702`

### 3.5 Storage layer + migrations
- ✅ **DONE Phase 10** — homegrown `PRAGMA user_version` migrator over numbered `.sql` files; alembic rejected per `CRITIQUE_APPENDIX.md` §4; SQLAlchemy rejected per §11; Postgres dropped per §12. `SqliteStorage` holds one `sqlite3.Connection` per process, WAL, `check_same_thread=False`; writes wrap `with self._conn:` per `.claude/rules/storage.md` bullet 2. `STARTUP_RADAR_DB_URL` env var deferred — `cfg.output.sqlite.path` covers the single knob this tool needs.

### 3.6 Centralize parsing
`_AMOUNT_RE` + `_STAGE_RE` duplicated in `rss.py:16`, `hackernews.py:16`, `sec_edgar.py`, `deepdive.py`. Move to `parsing/funding.py`. Add `parse_amount("$2.5M") -> 2_500_000` with tests — current regex is lossy (no number returned).

---

## 4. Tier 3 — Production hardening

### 4.1 Tests (currently zero)
- **Unit:** `parsing/funding.py`, `filters.py` (pure functions, easy wins)
- **Integration:** Each source against recorded fixtures via **vcrpy** or **respx** — no live network in CI
- **E2E smoke:** `cli run --dry-run` exits 0 with seeded fixtures
- **Streamlit:** `streamlit.testing.v1.AppTest` for page render + interactions
- Target 70% line coverage on `sources/`, `filters.py`, `parsing/`

### 4.2 CI pipeline (`.github/workflows/ci.yml`)
On PR: ruff, mypy, pytest, build wheel. Separate from `daily.yml` (cron job). Add **dependabot** + **pip-audit** + **gitleaks**.

### 4.3 Observability ✅ Phase 11
- **structlog** (stdlib-bridged, via `startup_radar/observability/logging.py`). JSON when `CI=1` or `STARTUP_RADAR_LOG_JSON=1`, pretty `ConsoleRenderer` locally. `configure_logging(json: bool)` is called once per process (CLI `@app.callback`, dashboard shell). Handler is sentinel-tagged so repeat calls swap in place without wiping pytest's `LogCaptureHandler` — `caplog.records` just works in tests.
- Per-source counters persisted to a `runs` table (migration `0002_runs_table.sql`): `started_at`, `ended_at`, `items_fetched`, `items_kept`, `error`, `user_version_at_run`. `pipeline()` wraps each source in `try/except/finally` → `storage.record_run(...)`. `status` renders a `Per-source health:` block; `doctor` emits `⚠ source.<key>.streak` when `failure_streak > 2`.
- **Sentry SDK dropped from the plan.** Single-user local tool — `runs` table + `doctor` streak warning already surface source failures. `SENTRY_DSN` field stays on `Secrets(BaseSettings)` as a harmless placeholder for any future user who wants to wire it.

### 4.4 Retries + timeouts ✅ Phase 11 + Phase 13
- Retry helper: `startup_radar/sources/_retry.py` — ~40 LOC, 3 attempts, `(1, 2, 4)` s backoff, fixed exception tuple per call site. Logs `retry.backoff` at WARNING. No `tenacity` / `backoff` (per `CRITIQUE_APPENDIX.md` §7). Sleep goes through a module-local `_sleep` alias so tests can monkeypatch it without clobbering `time.sleep` process-wide.
- **✅ Phase 13** — all three HTTP sources route through the shared `httpx.Client` from `startup_radar/http.py::get_client(cfg)`. Timeout inherited from `cfg.network.timeout_seconds` (default `10`); `User-Agent` default set on the client; `sources/rss.py` fetches bytes via the client and calls `feedparser.parse(r.content)`, retiring the `socket.setdefaulttimeout` hack. Retry `on=` tuples swapped from `requests.RequestException` → `httpx.HTTPError`.
- **Deferred:** circuit-breaker semantics ("skip source for N runs after M failures") — the persistent `failure_streak` counter exists, wiring it into `pipeline()` as a skip gate is its own follow-up phase.

### 4.5 Rate limiting + politeness
SEC EDGAR requires `User-Agent` w/ contact and ≤10 req/s — verify compliance. Add `aiolimiter` per source.

### 4.6 Async pipeline
Sources are network-bound. `main.py` runs them serially (~1 min total). `asyncio.gather` over 4 sources = ~5× faster. Use `httpx.AsyncClient`.

### 4.7 Secrets hygiene
- `credentials.json` and `token.json` should live in `~/.config/startup-radar/` (XDG), not repo root
- GH Actions: keep secrets in `secrets.GMAIL_*`, write to runner temp dir, never commit (current workflow at lines 34-41 already does this — formalize)
- **gitleaks** pre-commit hook
- `.env` never committed; `.env.example` always

---

## 5. Tier 4 — Polish & growth

| Item | Detail |
|---|---|
| **Docs site** | MkDocs Material → GH Pages. `CONTRIBUTING.md`, `ARCHITECTURE.md`, `docs/sources/adding-a-source.md` |
| **Versioning** | `setuptools-scm` for git-tag versions |
| **Release** | `cz` (commitizen) for conventional commits + auto-changelog. GH Action: tag push → build wheel → publish PyPI + GH Release |
| **Unified scheduling** | `startup-radar schedule install` detects OS and writes the right unit (replaces 3 README sections) |
| **Dashboard auth** | Streamlit native auth or Cloudflare Access for any non-localhost deploy |
| **Skills decoupling** | `.claude/skills/deepdive/SKILL.md:15-20` reads `config.yaml` shape directly. Have skill call `startup-radar config show --json` instead — schema becomes the contract |

---

## 6. Claude Code coding harness (`.claude/`)

The current `.claude/` only has `skills/setup-radar/` and `skills/deepdive/`. Below is the full robust harness for a Python data pipeline.

### 6.1 Target structure
```
.claude/
├── settings.json                    # model, permissions, hooks, MCP, env
├── settings.local.json              # gitignored: dev-only overrides
├── CLAUDE.md                        # architecture, conventions (loaded every session)
├── agents/                          # task-specialized subagents
│   ├── source-implementer/SKILL.md  # adds a new data source
│   ├── filter-tuner/SKILL.md        # tunes filters.py against fixtures
│   ├── dashboard-page/SKILL.md      # adds a Streamlit page
│   └── migration-author/SKILL.md    # writes alembic migration
├── skills/
│   ├── setup-radar/SKILL.md         # existing: onboarding
│   ├── deepdive/SKILL.md            # existing: research
│   ├── run/SKILL.md                 # /run — pipeline shortcut
│   ├── doctor/SKILL.md              # /doctor — env validation
│   ├── add-source/SKILL.md          # scaffold new source file + tests
│   └── ship/SKILL.md                # lint+test+commit+PR
├── commands/                        # legacy slash commands (skills preferred)
├── hooks/
│   ├── pre-bash.sh                  # block dangerous bash
│   ├── post-edit.sh                 # auto-format on file write
│   ├── session-init.sh              # show git status + DB row counts
│   └── pre-commit.sh                # lint + test gate
├── output-styles/                   # optional terminal styling
└── statusline.sh                    # branch | model | last-run-age
```

### 6.2 `CLAUDE.md` (project context, ~150 lines max)
What goes in:
- Stack, package manager (uv), entry points (`startup-radar` CLI)
- Repo layout (paste tree)
- Core invariants: "all sources must subclass `Source`", "all DB writes via `Storage`", "no `print()` — use structlog"
- Common commands: `make test`, `startup-radar doctor`
- Known gotchas: SEC EDGAR rate limits, OAuth scope unification, GH Actions DB persistence pattern
- `@import` references for deeper docs:
  ```markdown
  For source-author guide: @docs/sources/adding-a-source.md
  For DB schema: @docs/ARCHITECTURE.md
  ```

What stays out: tutorials, full code examples, rotating state, secrets.

### 6.3 `.claude/settings.json` — permissions + hooks
```json
{
  "model": "claude-opus-4-7",
  "permissions": {
    "defaultMode": "default",
    "allow": [
      "Bash(uv run *)",
      "Bash(uv sync *)",
      "Bash(make *)",
      "Bash(pytest *)",
      "Bash(ruff *)",
      "Bash(mypy *)",
      "Bash(startup-radar *)",
      "Bash(alembic *)",
      "Bash(git status)",
      "Bash(git diff *)",
      "Bash(git log *)",
      "Bash(gh pr *)",
      "Read(./**)",
      "Edit(startup_radar/**)",
      "Edit(tests/**)",
      "Edit(docs/**)",
      "WebFetch(domain:docs.python.org)",
      "WebFetch(domain:streamlit.io)",
      "WebFetch(domain:sec.gov)"
    ],
    "deny": [
      "Bash(rm -rf *)",
      "Bash(git push --force *)",
      "Bash(git push * main)",
      "Edit(.env)",
      "Edit(token.json)",
      "Edit(credentials.json)",
      "Edit(startup_radar.db)"
    ]
  },
  "hooks": {
    "SessionStart": [{"matcher": "", "hooks": [
      {"type": "command", "command": "./.claude/hooks/session-init.sh"}
    ]}],
    "PreToolUse": [{"matcher": "Bash", "hooks": [
      {"type": "command", "command": "./.claude/hooks/pre-bash.sh", "timeout": 5}
    ]}],
    "PostToolUse": [{"matcher": "Edit|Write", "hooks": [
      {"type": "command", "command": "./.claude/hooks/post-edit.sh"}
    ]}],
    "Stop": [{"matcher": "", "hooks": [
      {"type": "command", "command": "./.claude/hooks/pre-commit.sh", "timeout": 60}
    ]}]
  },
  "statusLine": {"type": "command", "command": "bash .claude/statusline.sh"},
  "env": {"PYTHONPATH": "."},
  "includeCoAuthoredBy": true,
  "cleanupPeriodDays": 30
}
```

### 6.4 Hooks
- **`session-init.sh`** — prints git status, DB row counts, last successful run timestamp. Free orientation.
- **`pre-bash.sh`** — denies `rm -rf`, `git push --force`, anything touching `.env`/`token.json`. Exit 2 to block.
- **`post-edit.sh`** — runs `ruff format <changed-file>` async. No friction; just keeps things tidy.
- **`pre-commit.sh`** — on `Stop` event: runs `make ci`. Exit 2 forces Claude to fix before declaring done.

### 6.5 Subagents (`.claude/agents/`)
Task-specialized prompts that main Claude delegates to:
- **`source-implementer`** — given a new source spec, scaffolds `sources/X.py`, adds to `registry.py`, writes vcrpy fixtures, adds tests. Tools: Read/Edit/Write/Bash.
- **`filter-tuner`** — runs filter against fixtures, reports precision/recall, suggests tweaks. Tools: Read/Bash.
- **`dashboard-page`** — given a page spec, scaffolds `web/pages/N_name.py` with caching + state conventions.
- **`migration-author`** — given a schema change, writes an alembic migration with up + down, runs `alembic upgrade head` against a temp DB to verify.

### 6.6 Skills (`.claude/skills/`)
- Keep existing `setup-radar`, `deepdive`
- Add `run`, `doctor`, `add-source`, `ship` as thin wrappers around CLI commands so users get `/run`, `/doctor` etc.
- `ship` skill: runs `make ci`, generates conventional-commit message, opens PR via `gh`. Wraps the entire flow.

### 6.7 MCP servers (in `settings.json` `mcpServers`)
| Server | Why |
|---|---|
| `playwright` | Live-test the Streamlit UI (existing global rule already suggests this) |
| `context7` | Fast-moving deps (Streamlit, pydantic, httpx) — fetch up-to-date docs |
| `github` (via `gh` already) | PR/issue management; `gh` CLI suffices, no MCP needed |

### 6.8 Status line
```bash
#!/usr/bin/env bash
branch=$(git branch --show-current)
last_run=$(test -f logs/latest.log && stat -f %Sm -t %H:%M logs/latest.log || echo "—")
echo "🛰 ${branch} | last run: ${last_run} | $(uv pip show startup-radar | awk '/Version/ {print $2}')"
```

### 6.9 `AGENTS.md` (vs `CLAUDE.md`)
Brief index of subagents in `.claude/agents/` so main Claude knows what's delegatable. Keep it ~30 lines.

---

## 7. Severity-ranked execution order

| Order | Item | Effort | Payoff |
|---|---|---|---|
| 1 | Streamlit `@st.cache_data` | 30 min | HIGH (perf) |
| 2 | `pyproject.toml` + Typer CLI + entry-point | 1 day | HIGH (DX) |
| 3 | Pydantic config + `.env` | 0.5 day | HIGH (safety) |
| 4 | Source ABC + centralized parsing module | 0.5 day | HIGH (maintainability) |
| 5 | GH Actions DB persistence (commit-to-data-branch or Turso) | 1 day | HIGH (correctness) |
| 6 | CI pipeline: ruff + mypy + pytest + vcrpy fixtures | 2 days | HIGH (foundation) |
| 7 | `.claude/` harness: settings.json, hooks, subagents | 0.5 day | HIGH (future Claude DX) |
| 8 | Decompose `app.py` into `web/pages/` | 1 day | MED |
| 9 | Storage class + alembic migrations | 1 day | MED |
| 10 | structlog + retries + circuit breaker | 1 day | MED |
| 11 | Async pipeline | 0.5 day | MED |
| 12 | Dockerfile + compose + devcontainer | 0.5 day | MED |
| 13 | MkDocs site + release automation | 1 day | LOW |

**~10–13 engineering days** for full transformation. Items 1–7 (~6 days) get you 80% of the value: one CLI, validated config, tests, persistent DB, fast dashboard, future-Claude with guardrails.

---

## 8. Definition of done

A new contributor can:
1. `pipx install startup-radar`
2. `startup-radar init` → answer 5 prompts
3. `startup-radar doctor` → green
4. `startup-radar serve` → dashboard up
5. `make ci` → all green

A future Claude session in this repo can:
1. Read `CLAUDE.md` + `AGENTS.md` and know the architecture cold
2. Be blocked from `rm -rf`, force-push, editing secrets
3. Auto-format on save, auto-test on stop
4. Delegate source/dashboard/migration work to specialized subagents
5. See live status (branch, last run, version) in the status line

---
