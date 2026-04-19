# AGENTS.md

> Startup Radar — a single-user Python tool that aggregates startup-funding signals (RSS, HN, SEC EDGAR, optional Gmail), filters them, and serves a Streamlit dashboard.

## Commands

| Task | Command |
|---|---|
| Install runtime deps | `make install` |
| Install dev deps | `make install-dev` |
| Run pipeline once | `make run` (or `uv run startup-radar run`) |
| Scheduled run (cron/GH Actions) | `uv run startup-radar run --scheduled` |
| Open dashboard | `make serve` (or `uv run startup-radar serve`) |
| Research brief | `uv run startup-radar deepdive "Anthropic"` |
| Lint | `make lint` |
| Format in place | `make format` |
| Tests | `make test` |
| Full local CI | `make ci` |
| Quick env check | `make doctor` |

## Must do
- Use `make` targets when one exists; never reinvent.
- Use a logger; never `print()` in library code (`startup_radar/sources/`, `startup_radar/filters.py`, `sinks/`, `database.py`, `connections.py`).
- Wrap Streamlit DB reads in `@st.cache_data(ttl=60)`.
- Set `timeout=` on every `requests`/`httpx` call.
- Run `make ci` before declaring work done.

## Must NOT do
- Do not edit `.env`, `credentials.json`, `token.json`, `uv.lock`, or `*.db` files.
- Do not commit. Do not push. Do not force-push. Do not `rm -rf`. Surface the diff and let the user commit.
- Do not add new top-level scripts; extend `startup_radar/cli.py` (the Typer CLI, since Phase 4).
- Do not reintroduce `requirements.txt` — `pyproject.toml` + `uv.lock` are the source of truth (since Phase 2). Add deps via `uv add <pkg>`.
- Do not add Postgres, alembic, async, or auth — explicitly out of scope (`docs/CRITIQUE_APPENDIX.md` §12).

## Subagents (.claude/agents/)
- `source-implementer` — scaffold a new data source under `sources/`.
- `filter-tuner` — diagnose `filters.py` precision/recall against fixtures (read-only).
- `dashboard-page` — scaffold a new Streamlit page with caching + state conventions.

## More context
Claude Code-specific config and detailed conventions live in `.claude/`. See `.claude/CLAUDE.md` (loaded into every session) and `.claude/rules/*.md` (auto-loaded by file path).
