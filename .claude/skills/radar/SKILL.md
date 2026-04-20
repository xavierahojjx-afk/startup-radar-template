---
name: radar
description: State-aware orchestrator for Startup Radar. Detects repo state and routes to onboarding, pipeline run, dashboard serve, doctor, status, or backup. Single entry point — auto-invokable on app-intent phrases.
when_to_use: |
  User expresses intent about the Startup Radar application. Triggers:
  "run my radar" · "check for new funding" · "what's new" · "scan" · "fetch"
  "onboard me" · "set me up" · "first time setup"
  "open the dashboard" · "serve" · "show me the UI"
  "is it broken?" · "diagnose" · "doctor" · "something's wrong"
  "status" · "when did it last run" · "last run age"
  "back up my data" · "snapshot" · "save a copy"
  AUTO-INVOKE on these phrases. Do NOT auto-invoke for generic SWE tasks
  (commits, refactors, tests) — those route elsewhere.
allowed-tools: [Bash, Read, Write, Edit, Glob, Grep]
---

# /radar — state-aware orchestrator

Replaces: `/setup-radar` · `/run` · `/serve` · `/status` · `/doctor` · `/backup`.

Flow: **detect state → route by (state × intent) → execute action → report.**

## 1. Detect state (always first)

```bash
test -f config.yaml      && echo HAS_CONFIG=1 || echo HAS_CONFIG=0
test -f startup_radar.db && echo HAS_DB=1     || echo HAS_DB=0
test -f token.json       && echo HAS_TOKEN=1  || echo HAS_TOKEN=0
test -d .venv            && echo SYNCED=1     || echo SYNCED=0
uv run startup-radar status 2>/dev/null | tail -20 || echo STATUS_FAIL
```

## 2. Route

| Precondition | Intent words | → Action |
|---|---|---|
| `HAS_CONFIG=0` | any | Onboard |
| `SYNCED=0` | any | Install, then re-route |
| `HAS_CONFIG=1 HAS_DB=0` | any | Run → Serve |
| — | `run` · `check` · `scan` · `what's new` · `fetch` | Run |
| — | `serve` · `dashboard` · `open` · `show me` · `ui` | Serve |
| — | `broken` · `diagnose` · `error` · `ok?` · `doctor` | Doctor |
| — | `status` · `last run` · `how long` · `state` | Status |
| — | `backup` · `snapshot` · `save a copy` | Backup |
| — | `reset` · `start over` | Confirm → Backup → Onboard |
| ambiguous, last run >48h | — | Run → Serve |
| ambiguous, last run ≤48h | — | Serve |

## 3. Actions

### Onboard

First-time interview. Writes `config.yaml`, installs deps, runs pipeline once, serves dashboard.

**Rules**
- One question (or tight group) at a time. Never dump the whole interview.
- Show drafts before writing. Confirm.
- NEVER commit, push, or touch git.
- NEVER ask for API keys / OAuth secrets — walk user through creating their own.
- `config.yaml` already exists → ask: reconfigure / edit section / exit.

**Interview (ask in order)**

| # | Section | Fields (paths are `AppConfig` keys) |
|---|---|---|
| 1 | About you | `user.name`, `user.background` (one sentence — drives fit rationales) |
| 2 | Targets | `targets.roles` (list), `targets.seniority_exclusions` (list), `targets.locations` (list + "remote"), `targets.industries` (list, empty = all), `targets.min_stage` ∈ {pre-seed, seed, series-a, series-b, any}, `targets.large_seed_threshold_musd` (default 50) |
| 3 | Sources (free) | `sources.rss.enabled` · `sources.hackernews.enabled` · `sources.sec_edgar.enabled` — default all true |
| 4 | Sources (Gmail, opt-in, ~10 min) | See "Gmail walkthrough" below. Sets `sources.gmail.enabled` + `sources.gmail.label` |
| 5 | Output | SQLite+Streamlit (default, no action). Opt-in Sheets mirror: `output.google_sheets.enabled`, `output.google_sheets.spreadsheet_id` (existing sheet or offer to create) |
| 6 | LinkedIn (optional) | Path to connections CSV — or tell user: dashboard sidebar accepts drag-drop upload later. Sets `user.linkedin_csv_path` |
| 7 | Scheduling | GH Actions (recommended) · Windows Task · launchd · cron · manual. Match user OS. Point to `scheduling/` templates for non-GH options |
| 8 | DeepDive fit | `deepdive.fit_factors` weights (high/medium/low for: industry_match, funding_stage, location, role_fit_signals, founder_pedigree, vc_tier) · `deepdive.tier1_vcs` (list) · `deepdive.thresholds` (default strong=7.5, moderate=5.0) |

**Schema of record:** `startup_radar/config/schema.py` (pydantic `AppConfig`). If answers don't fit the schema, trust the schema.

**After interview**
1. Bootstrap from template: `cp config.example.yaml config.yaml`.
2. Overlay answers with Edit tool, section by section.
3. Show full YAML → confirm → write.
4. Install: `make install` (wraps `uv sync --all-extras`).
5. **First run is mandatory** (dashboard is empty without data): `uv run startup-radar run`. Wait for exit 0.
6. Ask: "Dashboard now, or Sheets URL?" Default → Dashboard (run the Serve action).

**Gmail walkthrough (only if user chose Gmail)**

1. https://console.cloud.google.com/ → create project → enable Gmail API.
2. Create OAuth Desktop credentials → download → save as `credentials.json` in repo root. (Tell user; do NOT handle the file yourself.)
3. User creates a Gmail label (suggest: "Startup Funding") + filters so curated-newsletter senders auto-label.
4. Suggest subscriptions: StrictlyVC (`connie@strictlyvc.com`), Term Sheet (`termsheet@mail.fortune.com`), Venture Daily Digest (`venturedailydigest@substack.com`).
5. Add label name to `sources.gmail.label`.
6. Offer to scaffold a custom parser in `startup_radar/sources/gmail.py` per newsletter — ask user to paste a sample email, then write the parser.
7. First pipeline run triggers OAuth consent → produces `token.json`. Expected.

### Install

```bash
make install
```

Post-condition: `SYNCED=1`. Continue routing.

### Run

```bash
uv run startup-radar run
```

| Exit | Meaning | Response |
|---|---|---|
| 0, N>0 new | success | Report count. Do NOT auto-chain Serve unless user said "and show me" / "and open it" |
| 0, 0 new | quiet news day — normal | Report as success, not failure |
| ≠0 | pipeline error | Surface last 20 lines of stderr → route to Doctor |

Scheduled mode (`--scheduled`): only when user says cron / automation / "unattended" / "as if scheduled". Adds file logging + 15 min timeout.

**Never** pass `--once` or flags user didn't ask for. **Never** tail `logs/` unless asked.

### Serve

Background only. Foreground hangs the conversation.

```bash
uv run startup-radar serve
```

Run with `run_in_background: true`. Default URL: `http://localhost:8501`. Tell user Streamlit prints "Local URL" in its background output when ready.

Stop: `pkill -f 'streamlit run'` when user says "stop the dashboard".

**Never** foreground. **Never** `open` / `xdg-open` — Streamlit already opens a browser. **Never** pass `--port` / `--reload` unless asked.

### Doctor

```bash
uv run startup-radar doctor
```

Default fast. Add `--network` only on "deep" / "full" / "network" / "check feeds reachable".

Translate exit 1:

| Failure line | Response |
|---|---|
| Missing `config.yaml` | → Onboard |
| Missing `credentials.json` / `token.json` for enabled Gmail | → Onboard (Gmail walkthrough subsection) |
| DB path not writable | Surface perms on `output.sqlite.path` dir. Do NOT auto-fix. |
| Source healthcheck fail | Suggest `--network` if fast was used, else → Run to see real error |

Exit 0 → "all green." Done.

**Never** auto-fix failures. Surface → route → user decides.

### Status

```bash
uv run startup-radar status
```

| Last-run age | Response |
|---|---|
| <24h | fresh — confirm, stop |
| 24–48h | staleish — mention cron cadence |
| >48h | stale — suggest Run, or `/data-branch-restore` |
| `(none)` | never — suggest Run |

All DB row counts zero → suggest Run (or `/data-branch-restore` on fresh fork clone).

Pure read. No side effects. Never auto-chain.

### Backup

Ask **posture first** (skip only if user already specified in their request):

> Keeping this local (personal recovery), sharing it somewhere, or just the DB?

| Posture | Flag |
|---|---|
| local | (none — includes `credentials.json` + `token.json`) |
| sharing | `--no-secrets` |
| just the DB | `--db-only` |

```bash
uv run startup-radar backup [--no-secrets|--db-only]
```

Report tarball path + size. Remind: `backups/` is gitignored — user must copy off-machine for offsite redundancy.

**Never** suggest committing the tarball. **Never** skip the posture prompt on habituation.

## Constraints (all actions)

- NEVER touch git. Commits route to `/ship`.
- NEVER edit `credentials.json`, `token.json`, `.env`, `uv.lock`, `*.db`.
- NEVER read or guess secrets — walk the user through creating their own.
- NEVER auto-chain actions unless the user's intent implied the chain ("run and show me" = Run + Serve; "run" alone ≠ auto Serve).
- Surface raw diagnostics before interpreting. Interpretation must be honest, not optimistic — empty DB on a fresh clone is "never run here," not "pipeline broken."
