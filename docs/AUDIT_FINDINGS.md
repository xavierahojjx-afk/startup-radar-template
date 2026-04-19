# Production Readiness Audit — Findings

> Snapshot: 2026-04-19. Cited line numbers reflect HEAD at audit time.

## Summary table

| Dimension | Severity | Key issue |
|---|---|---|
| Entry points | RESOLVED (Phase 4) | Single `startup-radar` console script exposes `run` / `serve` / `deepdive`; `run --scheduled` folds the old `daily_run.py` logging+timeout path. Old root scripts deleted. |
| Config / secrets | PARTIAL (Phase 5) | Schema validation via pydantic `AppConfig` (`startup_radar/config/`) — resolved. Secrets relocation + `.env` / `pydantic-settings` still open — Phase 13. |
| Database | HIGH | New `sqlite3.connect()` per operation across 33 functions; GH Actions cache key is broken |
| Error handling | MED-HIGH | Silent source failures via bare `except → print()`; `print()` over logging in `main.py` |
| Code structure | RESOLVED (Phase 3) | `Source` ABC + registry land; `AMOUNT_RE`/`STAGE_RE`/company regexes centralized in `startup_radar/parsing/funding.py`. `main.py` orchestration is one loop over `SOURCES`. |
| Testing | HIGH | Zero tests; no `tests/`, no `conftest.py`, no CI validation workflow |
| Dependencies | RESOLVED (Phase 2) | `requirements.txt` removed; `pyproject.toml` + `uv.lock` are authoritative. Optional `google` extras still always-imported when Gmail enabled — cleanup deferred to Phase 3. |
| Dashboard | HIGH | `app.py` is 1,104 lines; no `@st.cache_data`; `load_data()` re-queries entire DB on every rerun |
| Skills coupling | MED | `.claude/skills/deepdive/SKILL.md:15-20` hardcodes `config.yaml` shape |
| Packaging | RESOLVED (Phase 4) | `pyproject.toml` + `[project.scripts] startup-radar` + `setuptools-scm` git-tag versioning; `pipx install git+https://...` works. Dockerfile deferred to Phase 14. |
| Scheduling | HIGH | GH Actions cache key uses `${{ github.run_id }}` → DB never persists across runs |
| Bugs | MED | OAuth scope mismatch Gmail vs Sheets; naive dedup ("WeWork" ≠ "We Work"); inconsistent timeouts |

## Detailed findings

### 1. Entry points & UX friction (RESOLVED — Phase 4)
- Single `startup-radar` console script (`[project.scripts]` in `pyproject.toml` → `startup_radar.cli:app`).
- `startup-radar run` replaces `python main.py`; `startup-radar run --scheduled` replaces `python daily_run.py` (folds the file-logging + 15-min timeout + stdout-redirect path into `cli.py`).
- `startup-radar serve` wraps `streamlit run app.py`; `startup-radar deepdive COMPANY` replaces `python deepdive.py`.
- `deepdive.py` re-homed under `startup_radar/research/`; `main.py` and `daily_run.py` deleted. `Makefile` `run`/`serve` targets now delegate to the CLI.
- Still outstanding: `startup-radar init` / `doctor` / `status` / `backup` (Phase 7–8) and `schedule install` (Phase 14).

### 2. Configuration & secrets (PARTIAL — Phase 5)
- **RESOLVED (Phase 5):** `config_loader.py` replaced by pydantic `AppConfig` at `startup_radar/config/{schema,loader}.py`. Validation errors point at field paths; `extra="forbid"` catches YAML typos; typed attribute access across `cli.py`, `filters.py`, all 4 sources, `research/deepdive.py`, and `app.py`.
- **Still open (Phase 13):** `credentials.json` and `token.json` live in repo root (not gitignored as XDG dotfiles); `.env` + `pydantic-settings` for env-var consumers is deferred — no current env-var consumer today, so scaffolding an empty `BaseSettings` is dead code until structlog / Sentry land.
- `.github/workflows/daily.yml:34-41` writes secrets from repo secrets to files at runtime — fine, but undocumented contract.

### 3. Database & persistence (HIGH)
- `database.py:20-23` — every public function opens a fresh `sqlite3.connect()`. WAL is enabled (line 22) but the per-call connection pattern is wasteful with 33 functions
- No migrations. Schema bump = manual SQL.
- Dashboard re-queries entire DB on every Streamlit rerun (`app.py:58`)
- **GH Actions cache is broken**: `.github/workflows/daily.yml:24-29` keys cache by `${{ github.run_id }}` (always unique). Restore-key fallback (`startup-radar-db-`) recovers the most recent cache non-deterministically — race condition between concurrent runs. Artifact upload (lines 49-50) is not used as the source of truth.

### 4. Error handling & observability (MED-HIGH)
- Silent failures: `sources/rss.py:94`, `sources/hackernews.py:45`, `sources/sec_edgar.py:49` — bare `except → print()`. A dead feed is indistinguishable from a slow news day in dashboard output.
- `daily_run.py:25-39` sets up file+console logging properly
- But `main.py` uses `print()` 40+ times, redirected through a `_LogStream` wrapper at `daily_run.py:42-58` — workaround, not a design pattern
- No retries, no circuit breakers, no metrics, no alerting

### 5. Code structure & reuse (RESOLVED — Phase 3)
- `Source` ABC at `startup_radar/sources/base.py`; all four built-ins (`rss`, `hackernews`, `sec_edgar`, `gmail`) subclass it.
- `SOURCES` registry at `startup_radar/sources/registry.py` — adding a source is one new file + one registry line.
- `AMOUNT_RE`, `STAGE_RE`, `COMPANY_SUBJECT_RE`, `COMPANY_INLINE_RE` consolidated into `startup_radar/parsing/funding.py`. New `parse_amount_musd("$2.5M") -> 2.5` lives there too (caller swap deferred to Phase 5).
- `_normalize_company` (formerly `main.py:22`) moves to `startup_radar/parsing/normalize.py` as `normalize_company` / `dedup_key`.
- `main.py` orchestration loop drops from ~50 lines (4 per-source blocks) to ~6 lines over `SOURCES`.
- `deepdive.py` was flagged here; its regex is independent and migrates with the module in Phase 4.
- `models.py` moved into the package (`startup_radar/models.py`); `filters.py` and `sinks/google_sheets.py` updated their imports.
- `filters.py` and `sinks/google_sheets.py` bodies untouched — they relocate in their own phases (5 / 11).

### 6. Testing (HIGH)
- Zero tests. No `tests/`, no `test_*.py`, no `conftest.py`
- `.github/workflows/daily.yml` is the cron job, not a CI workflow
- No linting, no type-checking, no unit-test stage

### 7. Dependency management (RESOLVED — Phase 2)
- `requirements.txt` removed; `pyproject.toml` + `uv.lock` are the source of truth.
- Dev deps under `[tool.uv] dev-dependencies`; `google` deps under `[project.optional-dependencies]`.
- Lockfile committed; `uv sync --all-extras` is the install command.
- Outstanding: optional `google` deps still imported eagerly when Gmail enabled — defer to Phase 3 with the Source ABC.

### 8. Dashboard `app.py` (HIGH)
- 1,104 lines, only 7 named functions; rest is procedural across 5 if-page blocks (line 203+)
- `st.rerun()` called 20+ times (lines 153, 185, 301, 333, 439, ...)
- `load_data()` (line 58) re-queries entire DB twice per rerun. Zero `@st.cache_data` decorators.
- Lines 54-58: data loaded globally
- Lines 140-185: sidebar
- Lines 203+: 5 page blocks deeply nested
- Form `key="ap_company"`, `key="ap_role"` (lines 702-703) collide on rerun, leaving stale values

### 9. Skills coupling (MED)
- `.claude/skills/setup-radar/SKILL.md` (~100 lines) — readable spec
- `.claude/skills/deepdive/SKILL.md` (~68 lines) — also readable
- `.claude/skills/deepdive/SKILL.md:15-20` reads `config.yaml` directly; `deepdive.py:5-8` imports `config_loader` — config schema change breaks both
- `reports/` dir created at runtime (`deepdive.py:26`), not at install/setup

### 10. Packaging & distribution (RESOLVED — Phase 4)
- `pyproject.toml` `[build-system]` uses setuptools + `setuptools-scm`; `[project.scripts]` registers `startup-radar = "startup_radar.cli:app"`.
- Version is `dynamic` — derived from git tag history with `fallback_version = "0.1.0"` for source-tarball builds.
- `uv.lock` committed; install is `git clone && make install` (wraps `uv sync --all-extras`) and the `startup-radar` shim lands on `$PATH`.
- `pipx install git+https://github.com/...` and `uv tool install .` both work.
- Still TODO: Dockerfile in Phase 14.

### 11. Scheduling (HIGH)
- GH Actions cache key issue (see #3)
- `scheduling/` has 3 OS-specific manual templates (`crontab.example`, `launchd.plist.template`, `windows_task.md`)
- No way to install/uninstall the scheduler programmatically
- DB persistence between scheduled runs is not guaranteed on GH Actions

### 12. Concrete bugs & smells

| # | Severity | Bug |
|---|---|---|
| 1 | MED | OAuth scope mismatch: `sinks/google_sheets.py:13` uses `spreadsheets`, `sources/gmail.py:30` uses `gmail.readonly` — single `token.json` cannot serve both. Undocumented. |
| 2 | MED | Dedup at `main.py:21` uses `re.sub(r"[\s.\-]+", "", s.company_name.lower())` — collapses "A.I."=="AI" but "WeWork"≠"We Work" |
| 3 | LOW | Streamlit form keys (`app.py:702-703`) don't clear after submit; stale values on next interaction |
| 4 | LOW | Only `sources/sec_edgar.py:46` sets an HTTP timeout (`timeout=20`); RSS and HN rely on `requests` defaults |
| 5 | LOW | `daily_run.py` stdout-redirect to logger via `_LogStream` is a workaround, not the right pattern |
