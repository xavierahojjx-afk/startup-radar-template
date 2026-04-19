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
| `startup-radar backup` → tarball of DB + config + token | Tier 1 | Single most important resilience feature for a personal tool. Trivial. |
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
| 8 | `startup-radar backup` + `doctor` + `status` | 0.5 day | Resilience. |
| 9 | GH Actions DB persistence via commit-to-data-branch | 1 day | Pick **one** option. |
| 10 | vcrpy fixtures + real source tests | 3-4 days | Underestimated in v1.0; cassette recording is fiddly. |
| 11 | Decompose `app.py` into `web/pages/` + cache wrappers | 2 days | Skip `components/` until ≥3 reuses. |
| 12 | Storage class + `PRAGMA user_version` migrator (NOT alembic) | 1 day | |
| 13 | structlog + retries + per-source failure counters | 1 day | |
| 14 | Dockerfile (single image, optional) | 0.5 day | |
| 15 | MkDocs site (optional) | 1 day | |

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
| 1 | **GH Actions DB persistence broken** — cache key uses `${{ github.run_id }}` (unique per run), restore is racy | `.github/workflows/daily.yml:24-29` | Drop `actions/cache`; commit DB to a `data` branch via `EndBug/add-and-commit`, or push to S3/Turso/GH Releases. Without this every "daily" run starts fresh. |
| 2 | **OAuth scope split** between Gmail (`gmail.readonly`) and Sheets (`spreadsheets`) — same `token.json` can't serve both | `sources/gmail.py:30`, `sinks/google_sheets.py:13` | Single OAuth client, merged scope list, single `token.json` |
| 3 | **Silent source failures** — exceptions swallowed to `print()`; dead feed reports 0 candidates indistinguishably from a slow news day | `sources/rss.py:94`, `hackernews.py:45`, `sec_edgar.py:49` | Structured logging w/ severity + per-source success counters surfaced in dashboard |
| 4 | **Naive dedup** — collapses spaces/dashes only ("WeWork" ≠ "We Work") | `main.py:21` | Normalized-name + canonical domain key in DB; index it |
| 5 | **Streamlit re-queries entire DB on every keystroke** — no caching | `app.py:58 load_data()` | `@st.cache_data(ttl=60)` — single biggest perf win, 30 minutes of work |
| 6 | **Inconsistent HTTP timeouts** — only EDGAR sets one (`timeout=20`) | `sources/sec_edgar.py:46` | Shared `httpx.Client` with default timeout, per-call override |

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
  storage/
    base.py                 # Storage Protocol
    sqlite.py               # current database.py, refactored
    postgres.py             # optional alternative
    migrations/             # alembic
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

Still open (Phase 13): secrets via `pydantic-settings` from `.env`. No current env-var consumer, so `Secrets(BaseSettings)` is deferred to alongside structlog + Sentry (`SENTRY_DSN` becomes the first tenant). `.env.example` will be committed then.

### 3.4 Dashboard decomposition
`app.py` is 1,104 lines and re-runs everything on every click. Move each page into `web/pages/N_name.py` (Streamlit native multi-page). Extract:
- `web/cache.py` — `@st.cache_data(ttl=60)` on all DB reads
- `web/components/` — company card, status pill, intro list (currently inline 3-4×)
- `web/state.py` — kills the `key="ap_company"` collisions noted at `app.py:702`

### 3.5 Storage layer + migrations
- Wrap raw `sqlite3` in a thin `Storage` class. One connection per process, WAL, `check_same_thread=False`. Currently `database.py:20-23` opens new connection per call across 33 functions.
- Add **alembic** for migrations. Bumping schema today requires manual SQL.
- Optional SQLAlchemy 2.x **Core** (not full ORM — keep it light) for type-safe queries.
- `STARTUP_RADAR_DB_URL=sqlite:///… | postgres://…` swappable. Postgres unblocks the GH-Actions persistence problem and enables team usage.

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

### 4.3 Observability
- **structlog** with JSON in prod, pretty in dev. Replace 40+ `print()` calls in `main.py`+sources and the `_LogStream` hack at `daily_run.py:42-58`
- Per-source counters: items fetched, items kept, errors, duration. Persist to a `runs` table; render last 30 days on a "System Health" dashboard page
- Optional **Sentry** SDK gated behind `SENTRY_DSN`

### 4.4 Retries + timeouts
- All HTTP via shared `httpx.Client` with `tenacity` retry decorator (3× exp backoff on 5xx/timeout/connection error) and explicit per-source timeouts
- Circuit breaker per source: 3 consecutive failures → skip for 1 run, log warning to dashboard

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
