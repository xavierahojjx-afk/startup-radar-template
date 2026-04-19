---
paths:
  - "startup_radar/sources/**"
---

# Source-author rules

- **Must:** every source subclasses `startup_radar.sources.base.Source`, sets class-level `name` + `enabled_key`, and implements `def fetch(self, cfg: AppConfig) -> list[Startup]` (Phase 5 typed the signature — import `AppConfig` from `startup_radar.config`).
- **Must:** every source registers itself in `startup_radar/sources/registry.py` — adding a source = one new file + one entry in `SOURCES`.
- **Must:** every HTTP call passes `timeout=` (or uses the shared client). `feedparser` is an exception — set `socket.setdefaulttimeout()` at module load (see `startup_radar/sources/rss.py`).
- **Must:** SEC EDGAR requests include `User-Agent: <Name> <email>` header (see `startup_radar/sources/sec_edgar.py`).
- **Must:** funding regexes (`AMOUNT_RE`, `STAGE_RE`, `COMPANY_SUBJECT_RE`, `COMPANY_INLINE_RE`) live in `startup_radar/parsing/funding.py` — never re-introduce duplicates inside source modules.
- **Never:** swallow exceptions to `print()`. Catch in `fetch()`, log via `logging.getLogger(__name__).warning("source.fetch_failed", extra={"source": self.name, ...})`, return `[]`. Never raise out of `fetch()`.
- **Never:** hardcode feed URLs in source code. Read from the typed sub-model (e.g. `cfg.sources.rss`, `cfg.sources.hackernews`) — attribute access, not dict lookup.
- **Never:** read `os.environ` directly inside a source. Pull from `cfg`.
- **Must:** any new source ships with a vcrpy cassette under `tests/fixtures/cassettes/<name>/` and a happy-path + empty-response test (Phase 10 dependency; flag if blocked).
- **Must:** the company name produced by a source is the raw name as it appears in the wild — `normalize_company` / `dedup_key` in `startup_radar/parsing/normalize.py` handles canonicalization. Don't normalize twice.
