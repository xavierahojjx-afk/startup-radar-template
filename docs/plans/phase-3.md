# Phase 3 Execution Plan — Source ABC + parsing module + registry

> Create `startup_radar/` package. Land a `Source` ABC, a registry, and centralized parsing helpers (funding regexes + company-name normalization). Refactor the four existing sources to subclass `Source`. Collapse `main.py`'s four ~12-line per-source blocks into a single loop over `SOURCES`. Leaves dashboard, storage, filters, and config at repo root — those move in Phases 11 / 12 / 5 respectively.

## Phase summary

- Create `startup_radar/__init__.py` (the real package — Phase 2 left a flat layout with `[tool.setuptools] py-modules`).
- Create `startup_radar/sources/{__init__.py, base.py, registry.py, rss.py, hackernews.py, sec_edgar.py, gmail.py}`.
- Create `startup_radar/parsing/{__init__.py, funding.py, normalize.py}`.
- Move `models.py` → `startup_radar/models.py`. Five callers update their imports.
- Each source becomes a `Source` subclass with `name`, `enabled_key`, `fetch(cfg) -> list[Startup]`, `healthcheck() -> bool`. The free-function `fetch(...)` shapes go away; `main.py` no longer cares about per-source argument lists.
- Centralize `_AMOUNT_RE`, `_STAGE_RE`, `_COMPANY_RE` (currently duplicated in `rss.py`, `hackernews.py`, `gmail.py`) into `startup_radar/parsing/funding.py`. Also expose `parse_amount_musd(s) -> float | None` so the lossy "amount as string" pattern can start retiring.
- Centralize `_normalize_company` + `dedup_key` (currently in `main.py:22`) into `startup_radar/parsing/normalize.py`. Both `main.py` and (later) the dashboard's tier-2 intro lookup will pull from here.
- Replace `print(f"  {SOURCE} error: ...")` swallowed-exception pattern with `logging.getLogger(__name__).warning(...)` per `.claude/rules/observability.md`.
- Delete the legacy `sources/` directory at repo root **after** the new package is wired and `make ci` is green.
- Update `pyproject.toml`'s `[tool.setuptools]` block to drop `py-modules` (still needed for the loose top-level files: `main`, `daily_run`, `app`, `database`, `filters`, `config_loader`, `connections`, `deepdive`) and add a `packages = ["startup_radar", "startup_radar.sources", "startup_radar.parsing"]` entry. Keep `py-modules` for the *not-yet-migrated* files.

## Out of scope (deferred)

| Item | Deferred to | Why |
|---|---|---|
| Move `database.py` into `startup_radar/storage/` | Phase 12 | Storage class + `PRAGMA user_version` migrator is its own phase. Touching DB layout now risks colliding with that work. |
| Move `app.py` into `startup_radar/web/pages/` | Phase 11 | 1,104-line decomposition is its own multi-day phase. |
| Move `filters.py` into `startup_radar/` | Phase 5 | Pydantic config rework rewrites the filter constructor; pull both moves into one diff there. |
| Move `config_loader.py` → `startup_radar/config/` | Phase 5 | Pydantic schema replaces it; rename happens in the same diff. |
| Move `connections.py` (LinkedIn intro lookup) | Phase 11 | It's UI-coupled — moves with the dashboard split. |
| Move `deepdive.py` → `startup_radar/research/` | Phase 4 | Typer CLI exposes `startup-radar deepdive` and re-homes the module in the same diff. |
| Move `main.py` / `daily_run.py` → `startup_radar/cli.py` | Phase 4 | Typer CLI replaces both entry points. |
| `parse_amount_musd` returning `Decimal` instead of `float` | Phase 12 | Storage typing decision — make the shape change once, not twice. |
| `setuptools-scm` git-tag versioning + `[project.scripts]` entry-point | Phase 4 | Per Phase 2 plan deferral — both attach to the Typer CLI. |
| Per-source failure counters persisted to a `runs` table | Phase 13 | structlog + retries phase. For now, log at WARNING; counters are in-memory only. |

## Effort estimate

- 0.5 engineering day sequential (matches refactor plan §0a slot 5 estimate).
- Critical path: refactoring all four sources to the ABC + smoke-running `make run` against a real config. The free-function-to-class flip is mechanical; the regression risk is in `main.py`'s orchestration loop.
- Tag at end as `phase-3`.

## Prerequisites

- ✅ Phase 2: `pyproject.toml` + `uv.lock` are dependency source of truth (commit `2a04d61`, tag `phase-2`).
- ✅ `make ci` green at start.
- ✅ Working tree clean.
- Nothing new to install — all parsing changes are stdlib + existing deps.

---

## 1. Files to change

| Path | Action | Notes |
|---|---|---|
| `startup_radar/__init__.py` | **create** | Empty (or one `__version__ = "0.1.0"` line — kept consistent with `pyproject.toml`). |
| `startup_radar/models.py` | **create** (moved) | Verbatim copy of root `models.py`. |
| `models.py` | **delete** | After all callers updated. |
| `startup_radar/sources/__init__.py` | **create** | Docstring only. |
| `startup_radar/sources/base.py` | **create** | `Source` ABC. ~30 lines. |
| `startup_radar/sources/registry.py` | **create** | `SOURCES: dict[str, Source]`. ~10 lines. |
| `startup_radar/sources/rss.py` | **create** (rewritten) | Subclass of `Source`. Uses `parsing.funding`. |
| `startup_radar/sources/hackernews.py` | **create** (rewritten) | Same pattern. |
| `startup_radar/sources/sec_edgar.py` | **create** (rewritten) | Same pattern. |
| `startup_radar/sources/gmail.py` | **create** (rewritten) | Same pattern. Imports `database` (still flat at root) for processed-id tracking. |
| `sources/` (root dir) | **delete** | Whole directory — `__init__.py`, `rss.py`, `hackernews.py`, `sec_edgar.py`, `gmail.py`. |
| `startup_radar/parsing/__init__.py` | **create** | Docstring only. |
| `startup_radar/parsing/funding.py` | **create** | `_AMOUNT_RE`, `_STAGE_RE`, `_COMPANY_SUBJECT_RE`, `parse_amount_musd()`. |
| `startup_radar/parsing/normalize.py` | **create** | `_LEGAL_SUFFIX_RE`, `normalize_company()`, `dedup_key()`. |
| `main.py` | edit | Orchestration loop collapses to ~10 lines over `SOURCES`. Drop `_normalize_company`, `_dedup` (now in `parsing.normalize`). Update `from models import` → `from startup_radar.models import`. |
| `database.py` | edit (imports) | `from models import Startup` → `from startup_radar.models import Startup`. No logic change. |
| `filters.py` | edit (imports) | Same import update. |
| `app.py` | edit (imports) | Same import update. |
| `deepdive.py` | edit (imports) | Same import update if present. |
| `daily_run.py` | edit (imports) | Same import update if present. |
| `pyproject.toml` | edit | Add `packages = ["startup_radar", "startup_radar.sources", "startup_radar.parsing"]`; trim `py-modules` to drop `"models"`. |
| `.claude/CLAUDE.md` | edit | Repo layout section: show `startup_radar/sources/`, `startup_radar/parsing/`, `startup_radar/models.py`. Update invariants pointing at the old `sources/` paths. |
| `.claude/rules/sources.md` | edit | Drop "(until the Source ABC lands in Phase 5)" weasel-clause; restate as a hard rule. Update "duplicated in `rss.py:18`, `hackernews.py:16`, ...; extract to `parsing/funding.py` (Phase 5)" to "live in `startup_radar/parsing/funding.py` — never re-introduce duplicates in source modules." |
| `.claude/agents/source-implementer/SKILL.md` | edit | Update scaffold path from `sources/<name>.py` to `startup_radar/sources/<name>.py`; show Source-subclass scaffold instead of free `fetch()`. |
| `tests/test_smoke.py` | edit | Add a smoke test that imports the registry and asserts `set(SOURCES.keys()) >= {"rss", "hackernews", "sec_edgar"}`. |
| `tests/parsing/__init__.py` | **create** | New test subdir. |
| `tests/parsing/test_funding.py` | **create** | Unit tests for `parse_amount_musd("$2.5M") == 2.5`, `("$1B") == 1000`, `("") is None`. |
| `tests/parsing/test_normalize.py` | **create** | `normalize_company("OpenAI") == normalize_company("Open AI Inc.")` (the canonical "OpenAI vs Open AI Inc." case from `docs/CRITIQUE_APPENDIX.md`). |
| `docs/AUDIT_FINDINGS.md` | edit | Mark §5 (code-structure / `_AMOUNT_RE` duplication) as RESOLVED. |
| `docs/PRODUCTION_REFACTOR_PLAN.md` | edit | §0a slot 5 marked done. |
| `docs/plans/phase-3.md` | create | This document. |

### Files explicitly NOT to touch

- `sinks/google_sheets.py` — sinks aren't part of the Source ABC. Phase 11/13 may move them; leave alone.
- `scheduling/` — out of scope.
- `database.py` body — only the `from models import` line changes.
- `filters.py` body — only the `from models import` line changes.
- `.github/workflows/daily.yml` — invocation stays `uv run python daily_run.py`; the orchestration moves under the hood, not the entry point.
- `.claude/hooks/*` — no change.

---

## 2. New file shapes

### 2.1 `startup_radar/sources/base.py`

```python
"""Source ABC. Every data source subclasses this and registers itself in registry.py."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from startup_radar.models import Startup


class Source(ABC):
    """Pluggable data source.

    Subclasses MUST set `name` (human-readable) and `enabled_key`
    (dotted path inside cfg["sources"]). `fetch(cfg)` is the only
    required method; `healthcheck()` is optional and returns True
    by default (Phase 6's `startup-radar doctor` will use it).
    """

    name: str
    enabled_key: str

    @abstractmethod
    def fetch(self, cfg: dict[str, Any]) -> list[Startup]:
        """Pull records and return zero or more Startup rows.

        On failure, log at WARNING and return []. Never raise out
        of this method — the orchestrator should never see a partial
        crash that aborts the whole run.
        """

    def healthcheck(self) -> bool:
        return True
```

### 2.2 `startup_radar/sources/registry.py`

```python
"""Source registry. Adding a source = one line here + one file in this directory."""

from __future__ import annotations

from startup_radar.sources.base import Source
from startup_radar.sources.gmail import GmailSource
from startup_radar.sources.hackernews import HackerNewsSource
from startup_radar.sources.rss import RSSSource
from startup_radar.sources.sec_edgar import SECEdgarSource

SOURCES: dict[str, Source] = {
    s.enabled_key: s
    for s in (RSSSource(), HackerNewsSource(), SECEdgarSource(), GmailSource())
}
```

`enabled_key` mirrors today's keys in `cfg["sources"]`: `"rss"`, `"hackernews"`, `"sec_edgar"`, `"gmail"`.

### 2.3 `startup_radar/parsing/funding.py`

```python
"""Funding-announcement regex helpers. Single source of truth — DO NOT duplicate elsewhere."""

from __future__ import annotations

import re

AMOUNT_RE = re.compile(r"\$\s*[\d,.]+\s*(?:B|M|billion|million)\b", re.IGNORECASE)
STAGE_RE = re.compile(r"\b(Pre-?Seed|Seed(?:\s+Round)?|Series\s+[A-F]\d?\+?)\b", re.IGNORECASE)
COMPANY_SUBJECT_RE = re.compile(
    r"^([A-Z][\w\-.&' ]{1,40}?)(?:\s+raises|\s+secures|\s+closes|\s+lands|\s+nabs|\s+announces|\s+picks up)",
    re.IGNORECASE,
)
COMPANY_INLINE_RE = re.compile(
    r"\b([A-Z][\w\-.&']{1,40}?)\s+(?:raises|raised|secures|closes|nabs|announces)\s+",
    re.IGNORECASE,
)

_AMOUNT_PARSE_RE = re.compile(r"\$?\s*([\d,.]+)\s*(m|million|b|billion)", re.IGNORECASE)


def parse_amount_musd(amount: str | None) -> float | None:
    """Parse '$2.5M' / '$1B' / etc. into millions of USD. Returns None if unparseable."""
    if not amount:
        return None
    m = _AMOUNT_PARSE_RE.search(amount)
    if not m:
        return None
    val = float(m.group(1).replace(",", ""))
    if m.group(2).lower().startswith("b"):
        val *= 1000
    return val
```

> Note: the existing per-source variants of `_STAGE_RE` differ slightly — `rss.py` allows `Seed Round`, `hackernews.py` and `gmail.py` only allow bare `Seed`. The unified `STAGE_RE` above takes the rss.py superset. Verify with the parsing unit tests in §1 that this doesn't change filter behavior.

### 2.4 `startup_radar/parsing/normalize.py`

```python
"""Company-name normalization for dedup. Single source of truth."""

from __future__ import annotations

import re

LEGAL_SUFFIX_RE = re.compile(
    r"[\s,]+(inc|incorporated|llc|l\.l\.c|ltd|limited|corp|corporation|co|company|gmbh|sa|ag|plc|holdings|labs?|technologies|tech)\.?$",
    re.IGNORECASE,
)


def normalize_company(name: str) -> str:
    """Canonical key for dedup. 'Open AI Inc.' → 'openai'."""
    name = name.lower().strip()
    prev = None
    while prev != name:
        prev = name
        name = LEGAL_SUFFIX_RE.sub("", name).strip()
    return re.sub(r"[\s.\-&']+", "", name)


def dedup_key(name: str) -> str:
    """Alias kept for callers that read clearer with this name."""
    return normalize_company(name)
```

### 2.5 `pyproject.toml` `[tool.setuptools]` update

```toml
[tool.setuptools]
packages = [
    "startup_radar",
    "startup_radar.sources",
    "startup_radar.parsing",
]
py-modules = [
    "main", "daily_run", "app", "deepdive",
    "database", "filters",
    "config_loader", "connections",
]
```

> `models` is removed from `py-modules` because it now lives at `startup_radar/models.py`. The remaining loose modules stay under `py-modules` until their respective phases (4 / 5 / 11 / 12) move them.

---

## 3. Source refactor pattern

### 3.1 `startup_radar/sources/rss.py` (illustrative)

```python
"""RSS source — pulls funding announcements from public feeds."""

from __future__ import annotations

import logging
import socket
from datetime import datetime
from typing import Any

import feedparser
from bs4 import BeautifulSoup

from startup_radar.models import Startup
from startup_radar.parsing.funding import (
    AMOUNT_RE, STAGE_RE, COMPANY_SUBJECT_RE,
)
from startup_radar.sources.base import Source

socket.setdefaulttimeout(20)

log = logging.getLogger(__name__)


def _strip_html(html: str) -> str:
    if not html:
        return ""
    return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)


def _extract_company(title: str) -> str:
    m = COMPANY_SUBJECT_RE.match(title)
    if m:
        return m.group(1).strip()
    # …existing fallback split-on-verbs logic…
    return ""


def _is_funding_item(title: str, summary: str) -> bool:
    text = f"{title} {summary}".lower()
    return any(s in text for s in (
        "raises", "raised", "funding", "series ",
        "seed round", "closes $", "secures $", "nabs $", "lands $",
    ))


class RSSSource(Source):
    name = "RSS"
    enabled_key = "rss"

    def fetch(self, cfg: dict[str, Any]) -> list[Startup]:
        rss_cfg = cfg.get("sources", {}).get(self.enabled_key, {})
        if not rss_cfg.get("enabled"):
            return []
        out: list[Startup] = []
        for feed in rss_cfg.get("feeds", []):
            try:
                out.extend(self._fetch_one(feed["url"], feed.get("name", feed["url"])))
            except Exception as e:
                log.warning("source.fetch_failed", extra={"source": self.name, "feed": feed.get("name"), "err": str(e)})
        return out

    def _fetch_one(self, feed_url: str, feed_name: str) -> list[Startup]:
        # …moved from current free-function fetch(); body unchanged…
        ...
```

### 3.2 Pattern across all four sources

| Source | Class | `enabled_key` | `name` | Notable |
|---|---|---|---|---|
| RSS | `RSSSource` | `"rss"` | `"RSS"` | feedparser; socket timeout at module load. |
| HN | `HackerNewsSource` | `"hackernews"` | `"Hacker News"` | reads `lookback_hours`, `queries` from cfg. |
| EDGAR | `SECEdgarSource` | `"sec_edgar"` | `"SEC EDGAR"` | reads `lookback_days`, `min_amount_musd`, `industry_sic_codes`. |
| Gmail | `GmailSource` | `"gmail"` | `"Gmail"` | imports `database` at function scope (still flat at root); google libs are an extra. |

---

## 4. `main.py` orchestration after the refactor

```python
"""Startup Radar — pipeline entry point."""

import logging
import sys
from datetime import datetime

import database
from config_loader import load_config
from filters import StartupFilter
from startup_radar.models import Startup
from startup_radar.parsing.normalize import dedup_key
from startup_radar.sources.registry import SOURCES

log = logging.getLogger(__name__)


def _dedup(startups: list[Startup]) -> list[Startup]:
    seen: set[str] = set()
    out: list[Startup] = []
    for s in startups:
        key = dedup_key(s.company_name)
        if key and key not in seen:
            seen.add(key)
            out.append(s)
    return out


def run() -> int:
    print("=" * 60)
    print("Startup Radar")
    print(f"Run time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    cfg = load_config()
    sqlite_cfg = cfg.get("output", {}).get("sqlite", {})
    if sqlite_cfg.get("enabled", True) and sqlite_cfg.get("path"):
        database.set_db_path(sqlite_cfg["path"])
    database.init_db()

    all_startups: list[Startup] = []
    for key, source in SOURCES.items():
        if not cfg.get("sources", {}).get(key, {}).get("enabled"):
            continue
        print(f"\n[{source.name}] Fetching...")
        found = source.fetch(cfg)
        print(f"  {len(found)} candidate(s)")
        all_startups.extend(found)

    print(f"\nTotal extracted: {len(all_startups)}")
    filtered = StartupFilter(cfg).filter(all_startups)
    print(f"After filter: {len(filtered)}")
    deduped = _dedup(filtered)
    if len(deduped) < len(filtered):
        print(f"After dedup: {len(deduped)}")

    # …existing fresh-vs-existing + insert + sheets-sink blocks unchanged…
```

The four ~12-line per-source blocks (lines 60-108 of current `main.py`) collapse to a 6-line loop. Adding a fifth source = one file under `startup_radar/sources/` + one entry in `registry.py` — no `main.py` edit.

---

## 5. Step-by-step execution

### 5.1 Pre-flight

```bash
git status                              # clean
git log -1 --format='%h %s'             # 2a04d61 feat(build):...
make ci                                 # green
```

### 5.2 Scaffold the package skeleton

Create in this order (parallel `Write` calls):
- `startup_radar/__init__.py`
- `startup_radar/sources/__init__.py`
- `startup_radar/parsing/__init__.py`

Then:
- `startup_radar/parsing/funding.py` (per §2.3)
- `startup_radar/parsing/normalize.py` (per §2.4)
- `startup_radar/sources/base.py` (per §2.1)

Smoke: `uv run python -c "from startup_radar.parsing.funding import parse_amount_musd; print(parse_amount_musd('$2.5M'))"` should print `2.5`.

### 5.3 Move `models.py` into the package

```bash
git mv models.py startup_radar/models.py
```

Then update imports in callers (parallel `Edit` calls):
```bash
grep -rn "from models import\|import models" --include="*.py" .
```
Expected hit list: `main.py`, `daily_run.py`, `database.py`, `filters.py`, `app.py`, `deepdive.py`, plus the four root `sources/*.py` files (which are about to be deleted anyway).

After updates, `uv run python -c "from startup_radar.models import Startup; Startup(company_name='x')"` should succeed.

### 5.4 Rewrite each source as a `Source` subclass

Order: `rss → hackernews → sec_edgar → gmail`. For each:
1. Write the new file under `startup_radar/sources/`.
2. Verify imports resolve via `uv run python -c "from startup_radar.sources.rss import RSSSource; RSSSource()"` (etc.).

Gmail is the trickiest — it imports `database` (still flat at root) inside `fetch()` for processed-id tracking. Keep that as a function-scope import.

### 5.5 Create the registry

`startup_radar/sources/registry.py` per §2.2.

Smoke:
```bash
uv run python -c "from startup_radar.sources.registry import SOURCES; print(sorted(SOURCES.keys()))"
# expect: ['gmail', 'hackernews', 'rss', 'sec_edgar']
```

### 5.6 Refactor `main.py`

Apply §4 shape. Delete the four per-source `if cfg.enabled` blocks; delete the local `_LEGAL_SUFFIX_RE` + `_normalize_company` (now in `parsing.normalize`).

### 5.7 Delete the legacy `sources/` directory

```bash
git rm -r sources/
```

> Same hook note as Phase 2 §5.4: the Stop hook (`pre-commit-check.sh`) blocks Edit/Write to specific paths but not `git rm`-driven directory removal.

### 5.8 Update `pyproject.toml`

Apply §2.5. Re-run `uv sync` to refresh the editable install:
```bash
uv sync --all-extras
uv run python -c "import startup_radar; from startup_radar.sources.registry import SOURCES; print(len(SOURCES))"
```

### 5.9 Add tests + run CI

Write the three new test files per §1 (`tests/parsing/test_funding.py`, `tests/parsing/test_normalize.py`, registry assertion in `test_smoke.py`). Then:

```bash
make ci         # ruff + format + mypy + pytest (now ≥7 tests)
make run        # pipeline end-to-end with real config — sanity only; failure ≠ block if config.yaml absent
```

If anything red: surface and pause. Common failure modes covered in §6.

### 5.10 Update harness + docs

Parallel Edit calls:
- `.claude/CLAUDE.md` — repo layout + invariants
- `.claude/rules/sources.md` — drop the "until Phase 5 lands" hedges
- `.claude/agents/source-implementer/SKILL.md` — new scaffold path + `Source` subclass template
- `docs/AUDIT_FINDINGS.md` — §5 marked RESOLVED
- `docs/PRODUCTION_REFACTOR_PLAN.md` — §0a slot 5 marked done

### 5.11 Ship

`/ship` skill. Suggested commit message:

```
feat(sources): introduce Source ABC, registry, and parsing module

Creates startup_radar/ package with sources/ and parsing/ subpackages.
Each source subclasses Source(name, enabled_key, fetch, healthcheck);
adding a source is now one file + one registry line.

Centralizes _AMOUNT_RE, _STAGE_RE, and the company-name normalizer
(formerly main.py:_normalize_company) into startup_radar/parsing/.
Kills the 3-way duplication across rss.py / hackernews.py / gmail.py
flagged in docs/AUDIT_FINDINGS.md §5.

main.py orchestration loop drops from ~50 lines (four per-source
blocks) to ~10 lines over SOURCES.

Defers Typer CLI (Phase 4), config rework (Phase 5), storage layer
(Phase 12), and dashboard split (Phase 11) — see plan §"Out of scope".
```

Then `STARTUP_RADAR_SHIP=1 git tag phase-3`.

---

## 6. Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Missed `from models import` import → ImportError at runtime | Medium | `make run` crashes | `make ci` catches via mypy/pytest collection; also grep-audit before deletion (§5.3). |
| 2 | Streamlit-cached `Startup` instances become incompatible after the dataclass moves | Low | Stale dashboard until restart | Document in commit body; user restarts streamlit. |
| 3 | `[tool.setuptools] packages` + `py-modules` together confuses setuptools | Medium | Build fails | Both keys are explicitly supported in setuptools ≥61. If it breaks, drop `py-modules` and rely on auto-discovery for the loose root files. |
| 4 | Unifying `STAGE_RE` (rss superset wins) changes filter rank for an HN/Gmail item | Low | Different filter outcome | Parsing unit tests pin `_stage_rank("Seed Round")` and `_stage_rank("Seed")`; both should rank as `1`. |
| 5 | `parse_amount_musd("$2.5M")` returning float vs current string-comparison code paths | Low | Filter regression in `filters._parse_amount_musd` | Phase 3 only ADDS `parse_amount_musd` to `parsing.funding` — `filters.py` keeps its own copy until Phase 5. No call-site swap yet. |
| 6 | Gmail source's `import database` at function scope breaks under the package layout | Low | Gmail fetch crashes | `database.py` stays at repo root; PYTHONPATH=. (already in `.claude/settings.json`) keeps the import working. |
| 7 | New `startup_radar/__init__.py` with `__version__` desyncs from `pyproject.toml` | Medium | Cosmetic until Phase 4 | Either skip `__version__` (defer to Phase 4 + setuptools-scm) or add a `# updated by Phase 4 setuptools-scm` comment. |
| 8 | `tests/parsing/__init__.py` collides with implicit-namespace pytest discovery | Low | Tests collected twice | Use a real `__init__.py`; `tests/__init__.py` already exists per Phase 0 scaffold (verify). |
| 9 | The `_extract_company` fallback split-on-verbs in `rss.py` doesn't migrate cleanly | Low | RSS company-name extraction regresses | Keep the helper module-private inside `startup_radar/sources/rss.py` — don't try to centralize "extract company from RSS title" — it's RSS-specific heuristic, not a parser. |
| 10 | `source-implementer` subagent doc rot — references pre-refactor scaffold | Certain | Future agent runs miss the new pattern | Updating `.claude/agents/source-implementer/SKILL.md` is part of §5.10. |

---

## 7. Done criteria

- [ ] `startup_radar/` package exists with `sources/` + `parsing/` subpackages.
- [ ] `Source` ABC defined; all four sources subclass it.
- [ ] `SOURCES` registry has exactly four entries: `rss`, `hackernews`, `sec_edgar`, `gmail`.
- [ ] `_AMOUNT_RE`, `_STAGE_RE`, company-name regexes exist in **one** place (`startup_radar/parsing/funding.py`).
- [ ] `normalize_company` lives in `startup_radar/parsing/normalize.py`; `main.py` no longer defines it.
- [ ] Legacy `sources/` directory deleted; legacy `models.py` deleted.
- [ ] `main.py` orchestration loop is one `for key, source in SOURCES.items()` block.
- [ ] `pyproject.toml` declares `packages = ["startup_radar", ...]`; `models` removed from `py-modules`.
- [ ] `make ci` passes (≥7 tests now: 4 smoke + funding parser + normalizer + registry).
- [ ] `make run` reaches "Total extracted: N" (actual N depends on `config.yaml`; absent config is fine).
- [ ] No `print()` calls in `startup_radar/sources/*.py` — only `logging.getLogger(__name__).warning(...)`.
- [ ] `.claude/rules/sources.md` updated; "until Phase 5" hedges removed.
- [ ] `.claude/agents/source-implementer/SKILL.md` shows `Source` subclass scaffold.
- [ ] `docs/AUDIT_FINDINGS.md` §5 marked RESOLVED.
- [ ] Commit tagged `phase-3`.

---

## 8. What this enables

- **Phase 4 (Typer CLI):** `cli.run()` becomes `for source in SOURCES.values(): source.fetch(cfg)` — five lines. The CLI also lifts `daily_run.py`'s logging into `startup_radar/observability/logging.py`.
- **Phase 5 (pydantic config):** the `Source.fetch(cfg: SourceConfigSchema)` signature can be tightened from `dict[str, Any]` to a typed schema in one place, not four.
- **Phase 6 (`startup-radar doctor`):** iterates `SOURCES.values()` calling `healthcheck()` on each. Today's "is the network reachable" question becomes per-source.
- **Phase 10 (vcrpy fixtures):** each `Source` subclass gets one cassette directory under `tests/fixtures/cassettes/<name>/`. Test scaffold is uniform — `dispatch a Source instance, assert non-empty list[Startup]`.
- **Phase 13 (structlog + retries):** `Source.fetch` already logs at WARNING with structured `extra={...}`; swapping `logging` for `structlog` is a 5-line `__init__` change in each source.
