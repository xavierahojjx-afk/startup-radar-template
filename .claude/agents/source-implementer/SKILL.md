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
1. Read `.claude/rules/sources.md` and `startup_radar/models.py` to understand the `Startup` shape.
2. Read `startup_radar/sources/base.py` (the `Source` ABC) and `startup_radar/sources/rss.py` as the cleanest reference pattern.
3. Create `startup_radar/sources/<name>.py` with a `Source` subclass:
   ```python
   from startup_radar.config import AppConfig
   from startup_radar.models import Startup
   from startup_radar.parsing.funding import AMOUNT_RE, STAGE_RE, COMPANY_SUBJECT_RE
   from startup_radar.sources.base import Source

   class XSource(Source):
       name = "X"
       enabled_key = "x"

       def fetch(self, cfg: AppConfig) -> list[Startup]:
           x_cfg = cfg.sources.x  # typed attribute access — add an `XConfig` sub-model in startup_radar/config/schema.py
           if not x_cfg.enabled:
               return []
           # …pull, parse, return list[Startup]…
   ```
4. Register in `startup_radar/sources/registry.py` — add the import and one entry to the `SOURCES` dict.
5. Add the matching sub-model to `startup_radar/config/schema.py` (e.g. `XConfig(_Strict)` with `enabled: bool = False` + source-specific fields) and wire it into `SourcesConfig`.
6. Add a vcrpy cassette skeleton under `tests/fixtures/cassettes/<name>/` and a `tests/unit/test_<name>.py` with one happy path + one empty-response test.
7. Surface to user: file diff, what config keys to add under `cfg.sources.<enabled_key>`, what to verify with `startup-radar run`.

## Constraints
- Never invent feed URLs — get them from the user.
- Always set HTTP `timeout=` (or `socket.setdefaulttimeout()` for `feedparser`).
- Never `print()` — log via `logging.getLogger(__name__).warning("source.fetch_failed", extra={"source": self.name, "err": str(e)})` and return `[]`.
- Never re-introduce `_AMOUNT_RE` / `_STAGE_RE` / company regexes in the source — import from `startup_radar.parsing.funding`.
- Never edit `pyproject.toml` deps or `uv.lock`; if a new dep is needed, surface it for the user to add via `uv add`.
