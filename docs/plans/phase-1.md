# Phase 1 Execution Plan — Claude Code Harness

> Establish a robust `.claude/` harness for `startup-radar-template` (single-user Python data pipeline + Streamlit dashboard) so future Claude sessions have safe defaults, fast feedback, codified conventions, and delegatable subagents. This plan is execution-ready — every section contains the exact bytes a follow-up session needs to write.

## Phase summary

- Scaffold a complete `.claude/` directory: `CLAUDE.md`, `settings.json`, `rules/`, `hooks/`, `agents/`, `statusline.sh`.
- Add an `AGENTS.md` at the repo root as a thin pointer file for agentic coding tools.
- Permissions are tightened per `docs/CRITIQUE_APPENDIX.md` §8: deny `Edit(uv.lock)`, `Bash(cat *.env)`, `Bash(cat *credentials*)`, etc.
- Hooks are calibrated to avoid friction: `Stop` runs lint+format only (NOT `make ci`); `PostToolUse` runs `ruff format` synchronously on the changed file only.
- Three subagents are added (`source-implementer`, `filter-tuner`, `dashboard-page`); `migration-author` is explicitly dropped per critique.

## Effort estimate

- 0.5 engineering day (4 hours) when executed sequentially.
- 1.5–2 hours when executed in parallel by 5–6 subagents (see §9).

## Prerequisites

- **Phase 0 must be complete.** That phase delivers:
  - `pyproject.toml` (so `uv run ruff format` and `make lint` exist). ✅ done in commit `b0ad818`.
  - `Makefile` with at minimum `make lint`, `make format`, `make test`, `make ci` targets. ✅ done.
  - `uv` installed and `uv.lock` present. ⚠️ NOT yet — Phase 0 deferred uv migration; hooks fall back to `ruff` directly if `uvx` missing.
- `jq` available on PATH (used by hooks to parse hook JSON input). If not present, hooks degrade gracefully (no-op).
- `git` repo initialized. ✅
- Existing `.claude/skills/setup-radar/SKILL.md` and `.claude/skills/deepdive/SKILL.md` MUST be left untouched.

---

## 1. Files to create

Exhaustive list. All paths relative to repo root. Do not create anything not on this list.

| Path | Purpose |
|---|---|
| `AGENTS.md` | Root-level command cheat-sheet + agent index for any agentic tool (Codex, Cursor, Claude). |
| `.claude/CLAUDE.md` | Per-session project context loaded on every start (~150 lines). |
| `.claude/settings.json` | Replaces existing 17-line stub. Adds model, hardened permissions, hooks, statusLine, env. |
| `.claude/rules/sources.md` | Conventions for files under `sources/` (Source ABC, dedup, parsing). |
| `.claude/rules/storage.md` | Conventions for `database.py` and any future `storage/`. |
| `.claude/rules/dashboard.md` | Conventions for `app.py` / future `web/pages/`. |
| `.claude/rules/observability.md` | structlog usage, no `print()`, per-source counters. |
| `.claude/rules/testing.md` | pytest layout, vcrpy fixtures, what to mock. |
| `.claude/hooks/session-init.sh` | SessionStart: prints branch, last-run age, DB row count. |
| `.claude/hooks/pre-bash.sh` | PreToolUse(Bash): blocks `rm -rf`, force push, secret reads. |
| `.claude/hooks/post-edit.sh` | PostToolUse(Edit\|Write): sync `ruff format` on the changed `.py` file. |
| `.claude/hooks/pre-commit-check.sh` | Stop: lint+format only (NO `make ci`); detects `print()`, bare `except:`, `os.getenv` in wrong dirs, hardcoded secrets, `requirements.txt` edits. |
| `.claude/agents/source-implementer/SKILL.md` | Subagent: scaffold a new data source. |
| `.claude/agents/filter-tuner/SKILL.md` | Subagent: tune `filters.py` against fixtures. |
| `.claude/agents/dashboard-page/SKILL.md` | Subagent: scaffold a new Streamlit page. |
| `.claude/statusline.sh` | Renders status line: branch \| last-run-age \| version. |
| `docs/plans/phase-1.md` | This document. |

**Files NOT to create in Phase 1** (deferred):
- `.claude/skills/run/`, `.claude/skills/doctor/`, `.claude/skills/add-source/`, `.claude/skills/ship/` — depend on the Typer CLI (Phase 6).
- `.claude/agents/migration-author/` — explicitly dropped (no alembic).
- `.claude/output-styles/`, `.claude/settings.local.json` — defer.
- MCP server config — defer until needs are concrete.

### 1.1 `.gitignore` adjustment (one-line edit, not a new file)

Append the following lines to `.gitignore` (verify they're not already present):

```
# Claude Code local overrides
.claude/settings.local.json

# ruff cache
.ruff_cache/
```

---

## 2. `.claude/CLAUDE.md` outline (~150 lines)

Use bullets, tables, code fences. No prose paragraphs.

### Section: Title + one-line purpose
- `# Startup Radar — Claude Context`
- One-sentence purpose: "Single-user Python tool that aggregates startup-funding signals from RSS/HN/SEC EDGAR/Gmail, filters them, and serves a Streamlit dashboard."

### Section: Stack (5–8 bullets)
- Python ≥3.10 (pyproject says 3.10+; eventual target 3.11).
- Package manager: `pip`/`uv` (Phase 4 migrates to uv lockfile).
- DB: SQLite, single file (`startup_radar.db`).
- Web: Streamlit (currently single-file `app.py`, ~1100 LOC).
- HTTP: `requests` today, migrating to `httpx` in Phase 13.
- Parsing: `feedparser`, `beautifulsoup4`.
- Configuration: `config.yaml` (validated by `config_loader.py` today; pydantic in Phase 7).
- Secrets: `credentials.json`, `token.json`, `.env` — never commit, never read.

### Section: Repo layout (paste tree)
- Embed current top-level: `main.py`, `app.py`, `daily_run.py`, `database.py`, `filters.py`, `models.py`, `config_loader.py`, `connections.py`, `deepdive.py`, `sources/`, `sinks/`, `scheduling/`, `tests/`, `docs/`.
- Note: target layout from `docs/PRODUCTION_REFACTOR_PLAN.md` §3.1 replaces this in later phases.

### Section: Core invariants (must/never block)
- Must: every new HTTP call uses an explicit timeout (`requests` `timeout=`, or shared `httpx.Client`).
- Must: every source returns `list[Startup]` (model in `models.py`).
- Must: company-name normalization goes through `_normalize_company` in `main.py:22` (until extracted to `parsing/normalize.py` in Phase 5).
- Never: `print()` outside `main.py`, `daily_run.py`, `deepdive.py`, or `tests/` — use a logger.
- Never: `os.getenv()` outside `config_loader.py` (later: `startup_radar/config/`).
- Never: edit `credentials.json`, `token.json`, `.env`, or `*.db` files.
- Never: edit `uv.lock` by hand — regenerate via `uv lock`.
- Never: edit `requirements.txt` once Phase 4 migrates to pyproject as source of truth.

### Section: Common commands
```bash
make lint              # ruff check
make format            # ruff format (writes)
make format-check      # ruff format --check (no writes)
make test              # pytest
make typecheck         # mypy
make ci                # lint + format-check + typecheck + test (run before /ship, NOT on every Stop)
make serve             # streamlit run app.py
make run               # python main.py
```

### Section: Gotchas (5–8 bullets)
- `feedparser` does NOT take a `timeout` kwarg — `sources/rss.py` uses `socket.setdefaulttimeout(20)` at module load.
- SEC EDGAR requires `User-Agent: Name email@example.com` header AND ≤10 req/s.
- Streamlit re-runs the entire script on every interaction — wrap DB reads in `@st.cache_data(ttl=60)` (already done in `app.py:59`).
- GH Actions cache for the SQLite DB is unsound (see `docs/CRITIQUE_APPENDIX.md` §1) — Phase 9 replaces with commit-to-data-branch.
- OAuth scopes for Gmail (`gmail.readonly`) and Sheets (`spreadsheets`) are now merged into a single `token.json` (Phase 0 fix).
- Dedup key strips legal suffixes (`inc`, `llc`, `corp`, etc.) — see `_LEGAL_SUFFIX_RE` in `main.py:16`.
- `sys.executable` was used at `app.py:804` without `import sys` until Phase 0 — lint catches this.

### Section: `@import` references
```markdown
For source-author conventions: @.claude/rules/sources.md
For storage/DB conventions: @.claude/rules/storage.md
For Streamlit conventions: @.claude/rules/dashboard.md
For logging/observability: @.claude/rules/observability.md
For test conventions: @.claude/rules/testing.md
For overall refactor plan: @docs/PRODUCTION_REFACTOR_PLAN.md
For critique/calibration: @docs/CRITIQUE_APPENDIX.md
```

### Section: Subagent index (one line each)
- `source-implementer` — scaffold a new data source under `sources/`.
- `filter-tuner` — diagnose `filters.py` precision/recall against fixtures.
- `dashboard-page` — scaffold a new Streamlit page (single-file or future multi-page).

### Section: What NOT to delegate
- Anything touching secrets, OAuth flows, or `config.yaml` writes — hand back to user.
- Commits and pushes — surface diff, let the user run `git commit`.

**Length budget:** 150 lines. If exceeded, trim Gotchas to 5 and shrink layout to top-level only.

---

## 3. `AGENTS.md` (root, ~50 lines) outline

Purpose: read by Codex, Cursor, future tools. Mirrors `CLAUDE.md` essentials.

### Sections
1. **Title** — `# AGENTS.md` + one-line repo purpose.
2. **Commands cheat-sheet** (table):
   | Task | Command |
   |---|---|
   | Install runtime deps | `make install` |
   | Install dev deps | `make install-dev` |
   | Run pipeline | `make run` (or `python main.py`) |
   | Open dashboard | `make serve` |
   | Lint + format check | `make lint` |
   | Format in place | `make format` |
   | Tests | `make test` |
   | Full local CI | `make ci` |
3. **Must do**:
   - Use `make` targets when one exists; never reinvent.
   - Use a logger; never `print()` in library code (`sources/`, `sinks/`, `database.py`, `filters.py`).
   - Wrap Streamlit DB reads in `@st.cache_data`.
   - Run `make ci` before declaring work done.
4. **Must not do**:
   - Do not edit `.env`, `credentials.json`, `token.json`, `uv.lock`, `*.db`.
   - Do not commit. Do not push. Do not force-push. Do not `rm -rf`.
   - Do not add new top-level scripts; extend `main.py` or the (forthcoming) Typer CLI.
   - Do not edit `requirements.txt` once Phase 4 makes `pyproject.toml` source of truth.
5. **Agent index** — three lines pointing at `.claude/agents/{source-implementer,filter-tuner,dashboard-page}/SKILL.md`.
6. **Pointer**: "Claude Code-specific config lives in `.claude/`. See `.claude/CLAUDE.md`."

**Length budget:** 50 lines.

---

## 4. `.claude/rules/*.md` content

Each file uses YAML frontmatter with `paths:` (Claude Code auto-loads when those paths are touched). Keep each file ≤30 lines, directive bullets only.

### 4.1 `.claude/rules/sources.md`
Frontmatter:
```yaml
---
paths:
  - "sources/**"
  - "startup_radar/sources/**"
---
```
Bullets:
- Must: every source exposes a `fetch(...)` callable returning `list[Startup]` (until the Source ABC lands in Phase 5).
- Must: every HTTP call passes `timeout=` (or uses the shared client).
- Must: SEC EDGAR requests include `User-Agent: <Name> <email>` header.
- Must: parsing helpers (`_AMOUNT_RE`, `_STAGE_RE`) live in a single module — do NOT redefine per source. (Today they're duplicated in `rss.py:18`, `hackernews.py:16`, `sec_edgar.py`, `deepdive.py`. Leave only when extending; flag for Phase 5 dedup.)
- Never: swallow exceptions to `print()`. Log with severity and re-raise or return `[]` plus a counted failure.
- Never: hardcode feed URLs in source code — read from `config.yaml`.
- Never: read `os.environ` directly inside a source — accept config dict argument.
- Must: any new source ships with a vcrpy cassette under `tests/fixtures/` (Phase 10 dependency; flag if blocked).

### 4.2 `.claude/rules/storage.md`
Frontmatter:
```yaml
---
paths:
  - "database.py"
  - "startup_radar/storage/**"
---
```
Bullets:
- Must: all SQL goes through `database.py` functions (no inline `sqlite3` in callers).
- Must: every write is wrapped in a single `with conn:` block (transactional).
- Must: schema changes bump `PRAGMA user_version` and ship a numbered `.sql` under `migrations/` (homegrown migrator — NOT alembic).
- Never: open a new connection inside a hot loop — accept `conn` as parameter or use module-level pooled connection.
- Never: edit `*.db` files directly. Use SQL.
- Must: any new column has a default value so old rows don't break.
- Must: indexes on any column used in `WHERE` of a query called from the dashboard.
- Never: store secrets in the DB. Use `.env` / `~/.config/startup-radar/`.

### 4.3 `.claude/rules/dashboard.md`
Frontmatter:
```yaml
---
paths:
  - "app.py"
  - "web/**"
  - "startup_radar/web/**"
---
```
Bullets:
- Must: every DB read in the dashboard is wrapped in `@st.cache_data(ttl=60)` (or shorter for write-heavy views).
- Must: session-state keys are defined as module-level constants (no inline string literals like `key="ap_company"`).
- Never: introduce a `web/components/` directory until ≥3 reuses exist (per `docs/CRITIQUE_APPENDIX.md` §7).
- Never: call HTTP/network from inside a Streamlit page render — fetch in pipeline, render from DB.
- Must: long-running operations (>500ms) use `st.spinner(...)`.
- Never: mutate global state inside a `@st.cache_data` function — return a new value.
- Must: when adding a multi-page app, follow Streamlit's `pages/` convention with the `N_name.py` numeric prefix.
- Must: any new page documents which session-state keys it reads/writes at the top of the file.

### 4.4 `.claude/rules/observability.md`
Frontmatter:
```yaml
---
paths:
  - "**/*.py"
---
```
Bullets:
- Must: use `structlog.get_logger(__name__)` for new modules (Phase 13). Until then, the existing `logging` setup is acceptable.
- Never: use `print()` in library code (`sources/`, `sinks/`, `database.py`, `filters.py`). `print()` is allowed in `main.py`, `daily_run.py`, `deepdive.py` until the Typer CLI lands.
- Never: bare `except:` or `except Exception:` without re-raising or logging at `error` level with traceback.
- Must: log fields are structured (`logger.info("source.fetched", source="rss", count=12)`), not formatted strings.
- Must: per-source success/failure increments a counter (Phase 13: persisted to `runs` table).
- Never: log secrets, OAuth tokens, full email bodies, or full `Authorization` headers.
- Must: HTTP errors include the URL and status code in the log record.

### 4.5 `.claude/rules/testing.md`
Frontmatter:
```yaml
---
paths:
  - "tests/**"
  - "**/test_*.py"
  - "**/conftest.py"
---
```
Bullets:
- Must: tests live under `tests/unit/` or `tests/integration/`. Filenames: `test_<module>.py`.
- Must: external HTTP is replayed via vcrpy cassettes in `tests/fixtures/cassettes/` — no live network in CI.
- Must: every new source ships at least one happy-path test and one empty-response test.
- Must: pure-function modules (`filters.py`, `parsing/funding.py`) target ≥90% line coverage; sources ≥70%.
- Never: write tests that touch the real `~/.config/` or write to repo-root files. Use `tmp_path`.
- Never: assert on log strings — assert on structured fields when structlog lands.
- Must: Streamlit tests use `streamlit.testing.v1.AppTest`, not Selenium/Playwright (deferred per critique §8).
- Must: a test that depends on Phase N work is marked `@pytest.mark.skip(reason="depends on Phase N")` until that phase ships.

---

## 5. `.claude/settings.json` — full content

REPLACES the existing `.claude/settings.json` (17-line stub).

```json
{
  "model": "claude-opus-4-7",
  "includeCoAuthoredBy": true,
  "cleanupPeriodDays": 30,
  "permissions": {
    "defaultMode": "default",
    "allow": [
      "Read",
      "Glob",
      "Grep",
      "Bash(uv run *)",
      "Bash(uv sync *)",
      "Bash(uv lock)",
      "Bash(uv pip show *)",
      "Bash(uv tool *)",
      "Bash(uvx *)",
      "Bash(make *)",
      "Bash(pytest *)",
      "Bash(ruff *)",
      "Bash(mypy *)",
      "Bash(python -m *)",
      "Bash(python3 -m *)",
      "Bash(streamlit *)",
      "Bash(git status)",
      "Bash(git status *)",
      "Bash(git diff)",
      "Bash(git diff *)",
      "Bash(git log *)",
      "Bash(git show *)",
      "Bash(git branch)",
      "Bash(git branch --show-current)",
      "Bash(git rev-parse *)",
      "Bash(gh pr list *)",
      "Bash(gh pr view *)",
      "Bash(gh pr diff *)",
      "Bash(gh issue list *)",
      "Bash(gh issue view *)",
      "Bash(ls *)",
      "Bash(pwd)",
      "Bash(wc *)",
      "Bash(sort *)",
      "Bash(uniq *)",
      "Bash(which *)",
      "Bash(stat *)",
      "Bash(mkdir -p *)",
      "Bash(.claude/hooks/*)",
      "Edit(startup_radar/**)",
      "Edit(sources/**)",
      "Edit(sinks/**)",
      "Edit(scheduling/**)",
      "Edit(tests/**)",
      "Edit(docs/**)",
      "Edit(.claude/**)",
      "Edit(app.py)",
      "Edit(main.py)",
      "Edit(daily_run.py)",
      "Edit(database.py)",
      "Edit(filters.py)",
      "Edit(models.py)",
      "Edit(config_loader.py)",
      "Edit(connections.py)",
      "Edit(deepdive.py)",
      "Edit(Makefile)",
      "Edit(pyproject.toml)",
      "Edit(README.md)",
      "Edit(AGENTS.md)",
      "Edit(.gitignore)",
      "Write(startup_radar/**)",
      "Write(sources/**)",
      "Write(sinks/**)",
      "Write(tests/**)",
      "Write(docs/**)",
      "Write(.claude/**)",
      "WebFetch(domain:docs.python.org)",
      "WebFetch(domain:streamlit.io)",
      "WebFetch(domain:docs.pydantic.dev)",
      "WebFetch(domain:typer.tiangolo.com)",
      "WebFetch(domain:www.sec.gov)",
      "WebFetch(domain:hn.algolia.com)",
      "WebFetch(domain:github.com)"
    ],
    "deny": [
      "Bash(rm -rf /)",
      "Bash(rm -rf ~)",
      "Bash(rm -rf *)",
      "Bash(rm -rf /tmp/*)",
      "Bash(rm -rf /tmp/test*)",
      "Bash(sudo *)",
      "Bash(chmod 777 *)",
      "Bash(curl * | sh)",
      "Bash(curl * | bash)",
      "Bash(wget * | sh)",
      "Bash(wget * | bash)",
      "Bash(cat *.env)",
      "Bash(cat .env*)",
      "Bash(cat *credentials*)",
      "Bash(cat *token.json*)",
      "Bash(cat *.db)",
      "Bash(cat *.sqlite*)",
      "Bash(git push --force *)",
      "Bash(git push -f *)",
      "Bash(git push origin main)",
      "Bash(git push origin master)",
      "Bash(git push * main)",
      "Bash(git push * master)",
      "Bash(git reset --hard *)",
      "Bash(git checkout -- *)",
      "Bash(git clean -f*)",
      "Bash(git config *)",
      "Bash(git commit *)",
      "Bash(pip install *)",
      "Bash(pip3 install *)",
      "Edit(.env)",
      "Edit(.env.*)",
      "Edit(token.json)",
      "Edit(credentials.json)",
      "Edit(uv.lock)",
      "Edit(*.db)",
      "Edit(*.sqlite)",
      "Edit(*.sqlite3)",
      "Edit(connections.csv)",
      "Edit(LinkedIn*.csv)",
      "Edit(.git/**)",
      "Write(.env)",
      "Write(.env.*)",
      "Write(token.json)",
      "Write(credentials.json)",
      "Write(uv.lock)",
      "Write(*.db)",
      "Write(.git/**)"
    ]
  },
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          { "type": "command", "command": ".claude/hooks/session-init.sh", "timeout": 5 }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command", "command": ".claude/hooks/pre-bash.sh", "timeout": 5 }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          { "type": "command", "command": ".claude/hooks/post-edit.sh", "timeout": 15 }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          { "type": "command", "command": ".claude/hooks/pre-commit-check.sh", "timeout": 30 }
        ]
      }
    ]
  },
  "statusLine": { "type": "command", "command": "bash .claude/statusline.sh" },
  "env": {
    "PYTHONPATH": ".",
    "PYTHONDONTWRITEBYTECODE": "1"
  }
}
```

Calibration notes (do NOT change without re-reading critique):
- `Bash(git commit *)` is **denied** — Claude must surface diffs and let user commit, or use future `/ship` skill.
- `Stop` timeout is 30s (lint+format only, well under 30s on this codebase).
- `PostToolUse` timeout is 15s (sync ruff format on a single file is sub-second; 15s leaves headroom).
- No MCP servers configured — defer to a later phase.

---

## 6. `.claude/hooks/*.sh` content

All scripts MUST start with `#!/usr/bin/env bash`, `set -uo pipefail` (NOT `-e`), and end with `exit 0` or `exit 2`. After writing: `chmod +x .claude/hooks/*.sh .claude/statusline.sh`.

### Exit-code contract (Claude Code hooks)
- `exit 0` — success, allow the action.
- `exit 2` — block the action; stderr shown to Claude as refusal reason.
- Any other non-zero — non-blocking warning printed to user.

### 6.1 `.claude/hooks/session-init.sh`
**Purpose:** SessionStart — print orientation info.

**Exit codes:** Always `exit 0`.

```bash
#!/usr/bin/env bash
set -uo pipefail

echo "=== Startup Radar — session init ==="

branch=$(git branch --show-current 2>/dev/null || echo "(not a git repo)")
echo "Branch: ${branch}"

if git rev-parse --git-dir >/dev/null 2>&1; then
  modified=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')
  echo "Uncommitted changes: ${modified} file(s)"
fi

if [ -d logs ] && ls logs/*.log >/dev/null 2>&1; then
  latest=$(ls -t logs/*.log 2>/dev/null | head -1)
  if [ -n "${latest}" ]; then
    age=$(stat -f '%Sm' -t '%Y-%m-%d %H:%M' "${latest}" 2>/dev/null || stat -c '%y' "${latest}" 2>/dev/null | cut -d. -f1)
    echo "Last pipeline log: ${latest} (${age})"
  fi
else
  echo "Last pipeline log: (none)"
fi

db=""
for candidate in startup_radar.db startups.db; do
  [ -f "${candidate}" ] && db="${candidate}" && break
done
if [ -n "${db}" ] && command -v sqlite3 >/dev/null 2>&1; then
  count=$(sqlite3 "${db}" "SELECT COUNT(*) FROM startups;" 2>/dev/null || echo "?")
  echo "DB rows (startups): ${count}"
fi

echo ""
echo "Read .claude/CLAUDE.md for conventions. Refactor plan: docs/PRODUCTION_REFACTOR_PLAN.md"
exit 0
```

### 6.2 `.claude/hooks/pre-bash.sh`
**Purpose:** Block dangerous bash (defense in depth on top of permissions deny-list).

**Exit codes:** `exit 2` to block; `exit 0` otherwise.

```bash
#!/usr/bin/env bash
set -uo pipefail

if ! command -v jq >/dev/null 2>&1; then
  exit 0
fi

cmd=$(jq -r '.tool_input.command // ""' 2>/dev/null)
if [ -z "${cmd}" ]; then
  exit 0
fi

deny_patterns=(
  'rm -rf (/|~|\$HOME|\*|\.\*)|Refusing destructive recursive delete.'
  'rm -rf /tmp|Refusing to wipe /tmp.'
  'sudo |No sudo. Ask the user to run privileged commands.'
  'chmod 777|Refusing world-writable chmod.'
  'curl .* \| (sh|bash)|Refusing pipe-to-shell.'
  'wget .* \| (sh|bash)|Refusing pipe-to-shell.'
  'git push.*--force|Refusing force push.'
  'git push.* (main|master)|Refusing direct push to main/master.'
  'git reset --hard|Refusing destructive reset.'
  'git config |Refusing to mutate git config.'
  'git commit |Refusing to commit. Surface the diff for user.'
  'cat .*\.env|Refusing to read .env files.'
  'cat .*credentials|Refusing to read credentials files.'
  'cat .*token\.json|Refusing to read token.json.'
  'pip install|Use `make install` or `uv add` — never raw pip install.'
  'pip3 install|Use `make install` or `uv add`.'
)

for pattern_reason in "${deny_patterns[@]}"; do
  pattern="${pattern_reason%%|*}"
  reason="${pattern_reason#*|}"
  if echo "${cmd}" | grep -qE "${pattern}"; then
    echo "BLOCKED by .claude/hooks/pre-bash.sh: ${reason}" >&2
    echo "  Command: ${cmd}" >&2
    exit 2
  fi
done

exit 0
```

### 6.3 `.claude/hooks/post-edit.sh`
**Purpose:** Sync format the changed file. Per critique §8: sync, not async; only the changed file.

**Exit codes:** Always `exit 0`. Formatter failures are warnings.

```bash
#!/usr/bin/env bash
set -uo pipefail

if ! command -v jq >/dev/null 2>&1; then
  exit 0
fi

file=$(jq -r '.tool_input.file_path // .tool_input.filePath // empty' 2>/dev/null)
if [ -z "${file}" ] || [ "${file}" = "null" ]; then
  exit 0
fi

case "${file}" in
  *.py) ;;
  *) exit 0 ;;
esac

case "${file}" in
  *.venv/*|*venv/*|*site-packages/*|*__pycache__/*) exit 0 ;;
esac

if command -v ruff >/dev/null 2>&1; then
  ruff format --quiet "${file}" 2>/dev/null || true
  ruff check --fix --quiet "${file}" 2>/dev/null || true
elif command -v uvx >/dev/null 2>&1; then
  uvx ruff format --quiet "${file}" 2>/dev/null || true
  uvx ruff check --fix --quiet "${file}" 2>/dev/null || true
fi

exit 0
```

### 6.4 `.claude/hooks/pre-commit-check.sh`
**Purpose:** Stop event — fast lint+format gate (NOT `make ci`). Surfaces anti-patterns introduced this session.

**Exit codes:** `exit 2` for critical (hardcoded secrets, `requirements.txt` edits when pyproject exists, `uv.lock` edits); `exit 0` otherwise.

```bash
#!/usr/bin/env bash
set -uo pipefail

if ! git rev-parse --git-dir >/dev/null 2>&1; then
  exit 0
fi

CHANGED=$( { git diff --name-only HEAD 2>/dev/null; git diff --cached --name-only 2>/dev/null; git ls-files --others --exclude-standard 2>/dev/null; } | sort -u | grep -v '^$' || true)

if [ -z "${CHANGED}" ]; then
  exit 0
fi

ISSUES=""
BLOCK=0

PY_FILES=$(echo "${CHANGED}" | grep -E '\.py$' || true)

# 1. print() in library code
if [ -n "${PY_FILES}" ]; then
  LIBRARY_PY=$(echo "${PY_FILES}" | grep -Ev '^(main\.py|daily_run\.py|deepdive\.py|tests/|\.claude/)' || true)
  if [ -n "${LIBRARY_PY}" ]; then
    PRINTS=$(echo "${LIBRARY_PY}" | xargs grep -lE '^[^#]*\bprint\(' 2>/dev/null | head -3 || true)
    if [ -n "${PRINTS}" ]; then
      ISSUES="${ISSUES}
WARN: print() in library code: ${PRINTS} — use a logger."
    fi
  fi
fi

# 2. bare except
if [ -n "${PY_FILES}" ]; then
  BARE=$(echo "${PY_FILES}" | xargs grep -lE 'except\s*:|except\s+Exception\s*:' 2>/dev/null | head -3 || true)
  if [ -n "${BARE}" ]; then
    ISSUES="${ISSUES}
WARN: bare/broad except in: ${BARE}"
  fi
fi

# 3. os.getenv outside config layer
if [ -n "${PY_FILES}" ]; then
  CONFIG_OK=$(echo "${PY_FILES}" | grep -Ev '^(config_loader\.py|startup_radar/config/)' || true)
  if [ -n "${CONFIG_OK}" ]; then
    ENV=$(echo "${CONFIG_OK}" | xargs grep -lE 'os\.getenv|os\.environ\b' 2>/dev/null | head -3 || true)
    if [ -n "${ENV}" ]; then
      ISSUES="${ISSUES}
WARN: os.getenv/os.environ outside config layer in: ${ENV}"
    fi
  fi
fi

# 4. hardcoded secrets
SECRET_PAT='(api_key|apikey|api-key|secret|password|passwd|token|bearer)\s*[:=]\s*["\047][A-Za-z0-9_\-]{16,}'
SECRETS=$(echo "${CHANGED}" | xargs grep -ilE "${SECRET_PAT}" 2>/dev/null | head -3 || true)
if [ -n "${SECRETS}" ]; then
  ISSUES="${ISSUES}
BLOCK: potential hardcoded secret in: ${SECRETS}"
  BLOCK=1
fi

# 5. requirements.txt edits when pyproject exists (Phase 4+)
if echo "${CHANGED}" | grep -q '^requirements\.txt$'; then
  if [ -f pyproject.toml ] && grep -q '^\[project\]' pyproject.toml 2>/dev/null; then
    ISSUES="${ISSUES}
BLOCK: requirements.txt edited but pyproject.toml exists. Edit pyproject.toml; regenerate via uv lock."
    BLOCK=1
  fi
fi

# 6. uv.lock manual edits
if echo "${CHANGED}" | grep -q '^uv\.lock$'; then
  ISSUES="${ISSUES}
BLOCK: uv.lock should not be hand-edited. Run \`uv lock\` to regenerate."
  BLOCK=1
fi

# 7. Run lint+format check (NOT full CI)
if [ -f Makefile ] && grep -q '^lint:' Makefile; then
  LINT_OUT=$(make lint 2>&1 || true)
  if echo "${LINT_OUT}" | grep -qE '(error|Error|ERROR|would reformat)'; then
    ISSUES="${ISSUES}

LINT FAILED:
${LINT_OUT}"
  fi
fi

if [ -n "${ISSUES}" ]; then
  printf "Pre-stop checks:\n%s\n" "${ISSUES}"
fi

if [ "${BLOCK}" -eq 1 ]; then
  exit 2
fi
exit 0
```

---

## 7. `.claude/agents/*/SKILL.md` content

Each subagent: YAML frontmatter (name, description, allowed-tools) + ≤40-line body.

### 7.1 `.claude/agents/source-implementer/SKILL.md`
```markdown
---
name: source-implementer
description: Use when adding a new data source to the Startup Radar pipeline. Scaffolds the source module, wiring, and a vcrpy fixture skeleton.
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash]
---

# source-implementer

## When to use
- User says "add an X source" or "fetch from Y feed".
- A new data source needs scaffolding: module, registration, parsing, tests.

## Process
1. Read `.claude/rules/sources.md` and `models.py` to understand the `Startup` shape.
2. Read `sources/rss.py` as the cleanest reference pattern.
3. Create `sources/<name>.py` exposing `def fetch(cfg: dict) -> list[Startup]`.
4. Wire into `main.py` (until the registry/ABC lands in Phase 5; then add to `sources/registry.py`).
5. Add a vcrpy cassette skeleton under `tests/fixtures/cassettes/<name>/` and a `tests/unit/test_<name>.py` with one happy path + one empty-response test.
6. Surface to user: file diff, what config keys to add, what to verify with `make run`.

## Constraints
- Never invent feed URLs — get them from the user.
- Always set HTTP timeout (or `socket.setdefaulttimeout()` for `feedparser`).
- Never `print()` — use the existing logger pattern.
```

### 7.2 `.claude/agents/filter-tuner/SKILL.md`
```markdown
---
name: filter-tuner
description: Use to diagnose or tune `filters.py` — measures precision/recall against fixtures and proposes targeted changes.
allowed-tools: [Read, Glob, Grep, Bash]
---

# filter-tuner

## When to use
- User says "filter is too strict / too loose" or "why was X dropped".
- Need to evaluate filter behaviour against a fixture or recent run.

## Process
1. Read `filters.py` and `config.yaml` (or `config.example.yaml`) to understand current rules.
2. Identify a fixture set: either the live DB (read-only) or `tests/fixtures/`.
3. Run a dry-run script: `python -c "from filters import StartupFilter; ..."` to compute kept/dropped counts.
4. Categorize drops: by source, by reason (stage, location, role, industry).
5. Propose a single-change diff with expected delta.

## Constraints
- Read-only — do NOT modify `filters.py` directly. Output a diff and rationale; let user accept.
- Never load secrets or hit the network.
```

### 7.3 `.claude/agents/dashboard-page/SKILL.md`
```markdown
---
name: dashboard-page
description: Use to scaffold a new Streamlit page or refactor a section of `app.py` into a discrete view.
allowed-tools: [Read, Write, Edit, Glob, Grep, Bash]
---

# dashboard-page

## When to use
- User says "add a page for X" or "extract the Y section of app.py".
- A new dashboard view needs caching + state conventions applied correctly.

## Process
1. Read `.claude/rules/dashboard.md` for caching/state rules.
2. Read the relevant section of `app.py` (currently ~1100 LOC).
3. Either (a) add a section to `app.py` if multi-page is not yet introduced, or (b) create `web/pages/N_<name>.py` if `web/` exists.
4. Wrap every DB read in `@st.cache_data(ttl=60)`.
5. Define session-state keys as module-level constants at the top of the file.
6. Add a `streamlit.testing.v1.AppTest`-based smoke test under `tests/unit/test_pages.py`.

## Constraints
- Never introduce `web/components/` until ≥3 reuses exist.
- Never make HTTP calls inside the render function — fetch in pipeline, render from DB.
```

---

## 8. `.claude/statusline.sh` content

```bash
#!/usr/bin/env bash
# Renders: 🛰 <branch> | last run: HH:MM | <version>
set -uo pipefail

branch=$(git branch --show-current 2>/dev/null || echo "?")

if [ -d logs ] && ls logs/*.log >/dev/null 2>&1; then
  latest=$(ls -t logs/*.log 2>/dev/null | head -1)
  last_run=$(stat -f '%Sm' -t '%H:%M' "${latest}" 2>/dev/null || stat -c '%y' "${latest}" 2>/dev/null | cut -d' ' -f2 | cut -d: -f1-2)
else
  last_run="—"
fi

if [ -f pyproject.toml ]; then
  version=$(grep -E '^version\s*=' pyproject.toml | head -1 | sed -E 's/.*"([^"]+)".*/\1/' || echo "?")
fi
[ -z "${version:-}" ] && version="dev"

echo "🛰 ${branch} | last run: ${last_run} | ${version}"
```

After writing: `chmod +x .claude/statusline.sh`.

---

## 9. Execution order within Phase 1

Phase 1 is highly parallelizable.

```
                       ┌─ rules/sources.md
                       ├─ rules/storage.md
                       ├─ rules/dashboard.md         ← independent leaves
                       ├─ rules/observability.md
                       ├─ rules/testing.md
                       │
.gitignore patch ──────┤
                       ├─ hooks/session-init.sh
                       ├─ hooks/pre-bash.sh          ← independent leaves
                       ├─ hooks/post-edit.sh
                       ├─ hooks/pre-commit-check.sh
                       │
                       ├─ statusline.sh              ← independent
                       │
                       ├─ agents/source-implementer/SKILL.md
                       ├─ agents/filter-tuner/SKILL.md
                       ├─ agents/dashboard-page/SKILL.md
                       │
                       ├─ AGENTS.md                  ← references all above
                       │
                       └─ CLAUDE.md                  ← references rules + agents
                            │
                            └─ settings.json         ← references hooks + statusline
                                  │
                                  └─ chmod +x on all .sh files
                                        │
                                        └─ Acceptance verification (§10)
```

### Parallel waves

**Wave A (5 subagents in parallel, ~10 min):**
1. Subagent 1 → `.claude/rules/sources.md`, `.claude/rules/storage.md`.
2. Subagent 2 → `.claude/rules/dashboard.md`, `.claude/rules/observability.md`, `.claude/rules/testing.md`.
3. Subagent 3 → `.claude/hooks/session-init.sh`, `.claude/hooks/pre-bash.sh`.
4. Subagent 4 → `.claude/hooks/post-edit.sh`, `.claude/hooks/pre-commit-check.sh`.
5. Subagent 5 → `.claude/agents/source-implementer/SKILL.md`, `.claude/agents/filter-tuner/SKILL.md`, `.claude/agents/dashboard-page/SKILL.md`, `.claude/statusline.sh`.

**Wave B (sequential, ~5 min):**
6. Append to `.gitignore`.
7. Write `AGENTS.md` (root).
8. Write `.claude/CLAUDE.md`.
9. Write `.claude/settings.json` (replaces existing 17-line stub).

**Wave C (sequential, ~1 min):**
10. `chmod +x .claude/hooks/*.sh .claude/statusline.sh`.
11. Run acceptance criteria (§10).

Subagents in Wave A do not touch each other's files.

---

## 10. Acceptance criteria

Run each check in order. All must pass before declaring Phase 1 complete.

### 10.1 File existence
```bash
for f in \
  AGENTS.md \
  .claude/CLAUDE.md \
  .claude/settings.json \
  .claude/statusline.sh \
  .claude/rules/sources.md \
  .claude/rules/storage.md \
  .claude/rules/dashboard.md \
  .claude/rules/observability.md \
  .claude/rules/testing.md \
  .claude/hooks/session-init.sh \
  .claude/hooks/pre-bash.sh \
  .claude/hooks/post-edit.sh \
  .claude/hooks/pre-commit-check.sh \
  .claude/agents/source-implementer/SKILL.md \
  .claude/agents/filter-tuner/SKILL.md \
  .claude/agents/dashboard-page/SKILL.md \
; do
  test -f "$f" || { echo "MISSING: $f"; exit 1; }
done
echo "All Phase 1 files present."
```

### 10.2 Executable bit on shell scripts
```bash
for f in .claude/hooks/*.sh .claude/statusline.sh; do
  test -x "$f" || { echo "NOT EXECUTABLE: $f"; exit 1; }
done
```

### 10.3 JSON validity
```bash
python3 -c "import json; json.load(open('.claude/settings.json'))" && echo "settings.json valid"
```

### 10.4 Manual session checks (open a fresh Claude Code session)
- **SessionStart hook fires:** session opens with `=== Startup Radar — session init ===` banner.
- **PreToolUse blocks:** ask Claude to run `rm -rf /tmp/test`. Expect: refused with "BLOCKED" message.
- **PreToolUse allows safe:** ask Claude to run `ls`. Expect: succeeds.
- **PostToolUse formats:** add a badly-formatted snippet to a scratch file. Expect: reformatted on save.
- **Rules auto-load:** edit `sources/rss.py`. Verify Claude references `.claude/rules/sources.md` conventions.
- **Stop hook lint+format only:** end a turn after a Python edit. Expect: `make lint` runs (≤5s); `make test` does NOT.
- **Stop hook blocks on hardcoded secret:** add `api_key = "sk-1234567890abcdef1234"`. Expect: blocked.
- **Stop hook blocks on requirements.txt edit:** modify `requirements.txt`. Expect: blocked (pyproject.toml exists).
- **Subagent delegation works:** ask Claude to delegate to `source-implementer`. Expect: subagent spawns and references `SKILL.md`.
- **Status line renders:** see `🛰 <branch> | last run: <time-or-—> | <version>` at bottom.

### 10.5 Git hygiene
```bash
git status --short  # Should show new .claude/ files but no edits to .env, token.json, *.db
grep -q '^\.claude/settings\.local\.json$' .gitignore && echo ".gitignore updated"
```

---

## 11. Risks & mitigations

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | `Stop` hook becomes noisy on trivial single-line clarifications | High | Friction within a week | Already mitigated: `Stop` does ONLY lint+format on changed files (not full `make ci`). If still noisy, add early no-op when `git diff` is empty. |
| 2 | Hook script crashes (jq missing, awk error) and blocks all Bash | Medium | Blocking | All hooks use `set -uo pipefail` (NOT `-e`), check for `command -v jq` and degrade to `exit 0`, wrap fallible pipes with `\|\| true`. Test with jq removed. |
| 3 | Permissions too restrictive — Claude asks for permission every turn | Medium | Friction | Allow-list is generous for `make *`, `git status/diff/log`, `python -m`, common reads. Add to allow-list as patterns surface (use `fewer-permission-prompts` skill). |
| 4 | Permissions too permissive — destructive command via path the deny-list misses | Low | Severe (data loss) | Defense in depth: `pre-bash.sh` re-checks dangerous patterns regardless of allow-list. |
| 5 | `post-edit.sh` introduces unintended diff Claude was preparing to commit | Medium | Confusion | Sync execution = Claude sees formatted version on next read. `.py` only; skip venv/pycache. |
| 6 | `CLAUDE.md` exceeds 150 lines — bloats every session's context | Low | Token waste | Hard budget: 150 lines. If exceeded, move detail into `.claude/rules/*.md` (path-gated) or `docs/`. |
| 7 | Subagent SKILL.md frontmatter wrong — agents don't load | Medium | Subagents unusable | Mirror `.claude/skills/setup-radar/SKILL.md` structure. Verify by listing available agents. |
| 8 | Status line `stat` flags differ macOS (`-f`) vs Linux (`-c`) | Medium | Status shows "?" | Mitigated: each `stat` has `\|\|` fallback. Test on both. |
| 9 | `.claude/settings.json` overwrite loses local user permissions | Low | Annoyance | Surface diff to user before overwrite. Original is in git, so recovery is `git diff`. |
| 10 | Hooks fire during read-only sessions and waste cycles | Low | Marginal | All hooks <1s except `Stop` (≤5s). Acceptable. |
| 11 | `Bash(git commit *)` denied — user expects `/ship` workflow | Medium | Workflow gap | Document in `AGENTS.md`: "to commit, run in your shell, not via Claude." Add `/ship` skill in Phase 6. |
| 12 | `pre-commit-check.sh` flags pre-existing `print()` in `sources/` etc. | High | Noisy first session | Acceptable — scope is `git diff HEAD` so only changed files surface. Either fix or accept as backlog. |

---

## End of Phase 1 plan

When verified per §10, proceed to:
- **Phase 2** (per refactor plan re-ordered slot 4): `pyproject.toml` + uv migration + Typer CLI scaffolding.
- After Phase 2: deferred `.claude/skills/{run,doctor,ship}/` skills become possible.
