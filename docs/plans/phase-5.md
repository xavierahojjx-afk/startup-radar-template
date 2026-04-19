# Phase 5 Execution Plan — Pydantic config + filters move

> Replace the 4-key-existence-check `config_loader.py` with a pydantic v2 `AppConfig` schema. Move `filters.py` into the package and retype its constructors to take `AppConfig`. Retype `Source.fetch(cfg)` and all 4 sources. Wire the existing `parse_amount_musd` from `startup_radar/parsing/funding.py` into `filters.py` (retires the duplicate `_parse_amount_musd`). Leaves `app.py` body untouched except for the handful of `cfg.get(...)` reads that would otherwise crash on an attribute-access AppConfig — full dashboard decomposition is still Phase 11.

## Phase summary

- Add `pydantic>=2.5` as a runtime dep.
- Create `startup_radar/config/{__init__.py, schema.py, loader.py}`:
  - `schema.py` — pydantic v2 models: `AppConfig` (root), `UserConfig`, `TargetsConfig`, `SourcesConfig` (with nested `RSSConfig + RSSFeed`, `HackerNewsConfig`, `SECEdgarConfig`, `GmailConfig`), `OutputConfig` (with `SQLiteConfig`, `GoogleSheetsConfig`), `ConnectionsConfig`, `DeepDiveConfig` (with `FitFactors`, `Thresholds`). All with `model_config = ConfigDict(extra="forbid")` to catch typos.
  - `loader.py` — `load_config(path: Path | None = None) -> AppConfig`. Same fallback-to-example behavior as today. `ConfigError` exception wraps `pydantic.ValidationError` with a friendly message that points at field paths.
- Delete root `config_loader.py` (no back-compat shim — there are only 4 known import sites, and Phase 5 updates all of them in the same diff).
- Move `filters.py` → `startup_radar/filters.py`:
  - `StartupFilter(cfg: AppConfig)` and `JobFilter(cfg: AppConfig)` — typed, attribute access (`cfg.targets.locations` instead of `cfg["targets"].get("locations", [])`).
  - Delete the module-local `_parse_amount_musd`; import `parse_amount_musd` from `startup_radar.parsing.funding`.
  - Update 1 caller (`cli.py`).
- Retype `Source.fetch(cfg)` in the ABC from `dict[str, Any]` to `AppConfig`; update all 4 sources (`rss.py`, `hackernews.py`, `sec_edgar.py`, `gmail.py`) to attribute access against the typed sub-models. Each source's `if not sources[x].enabled: return []` guard stays, just typed.
- Update remaining consumers to attribute access:
  - `startup_radar/cli.py::_pipeline` — `cfg.output.sqlite`, `cfg.sources`, `cfg.output.google_sheets`.
  - `startup_radar/research/deepdive.py` — `_score_company(info, cfg)` and `_generate_docx(..., cfg)` and the 2 remaining `load_config()` reads. Rewrite `cfg.get("deepdive", {}).get("fit_factors", {})` style to `cfg.deepdive.fit_factors` throughout.
  - `app.py` — 2 call sites (lines 27-28 and 219). Minimal diff: `cfg.output.sqlite.path` and `cfg.user.name`. Body of app.py stays in Phase 11.
- `pyproject.toml`:
  - Add `pydantic>=2.5` to `dependencies`.
  - Add `startup_radar.config` to `[tool.setuptools] packages`.
  - Drop `config_loader` and `filters` from `[tool.setuptools] py-modules`.
  - Expand `[tool.mypy] files` to include `startup_radar/config` and `startup_radar/filters.py`. Deliberately NOT `cli.py`, `app.py`, `deepdive.py` — see Phase 4 rationale (transitive `requests` import → stub noise).
- Tests:
  - `tests/config/__init__.py` + `tests/config/test_schema.py` — happy path parses `config.example.yaml`; missing required key raises `ConfigError`; unknown key raises `ConfigError`; type coercion for `min_amount_musd` / `lookback_days`.
  - `tests/test_filters.py` — smoke test `StartupFilter(AppConfig(**sample)).passes(Startup(...))`; seed-with-large-amount path still admits (regression guard for the `parse_amount_musd` swap).
- Update harness + docs: `.claude/CLAUDE.md`, `.claude/rules/sources.md`, `.claude/settings.json` allow-list, `.claude/hooks/pre-commit-check.sh`, `.claude/agents/source-implementer/SKILL.md`, `.claude/agents/filter-tuner/SKILL.md`, `.claude/skills/deepdive/SKILL.md`, `AGENTS.md`, `README.md`, `docs/AUDIT_FINDINGS.md`, `docs/PRODUCTION_REFACTOR_PLAN.md`.

## Out of scope (deferred)

| Item | Deferred to | Why |
|---|---|---|
| `.env` + `pydantic-settings` + `Secrets(BaseSettings)` | Phase 13 | The refactor plan §0a slot 7 bundles `.env` here, but there is literally zero env-var consumer today — OAuth uses `credentials.json`/`token.json` files, not env vars. Scaffolding an empty `BaseSettings` is dead code. Phase 13 (structlog + retries) introduces `SENTRY_DSN` and is the natural home. |
| `startup-radar admin config show --json` (skills-decoupling) | Phase 12 | Needs storage-layer cfg surfacing. Skills currently hardcode YAML shape; Phase 5 does NOT fix `.claude/skills/deepdive/SKILL.md:15-20` — only docs a known mismatch. |
| Move `config.example.yaml` into `startup_radar/config/` | Phase 12 | Keep it at repo root for discoverability by the `/setup` skill and first-run loader fallback. Package-data wiring is storage-layer complexity; defer. |
| Move `connections.py` / `database.py` / `app.py` into the package | Phases 11 / 12 / 11 | Same rationale as Phase 4 — one concern per phase. |
| Pydantic-driven CLI flags (`typer.Option` defaults from AppConfig) | Phase 7 | Wizard phase introduces the inverse direction (CLI writes config); tie them together. |
| Migrate `config.example.yaml` to include a `config_version: 1` field | Phase 12 | Pairs with `PRAGMA user_version` migrator; no consumer today. |
| Refactor the `cfg.get("deepdive", {}).get(...)` chains in `deepdive.py` into a cached helper object | Phase 13 | The rewrite is mechanical attribute-access in Phase 5; a caching layer is premature until retries/observability land. |
| Replace `print()` in `cli.py` / `deepdive.py` with structlog | Phase 13 | Phase 13 scope. |
| Retype `filters.JobFilter.filter` return against a typed `JobMatch` config surface | Phase 11 | `JobMatch` itself is UI-coupled — moves with dashboard decomposition. |

## Effort estimate

- 0.5–0.75 engineering day. Refactor plan §0a slot 7 estimated 0.5 day when paired with `.env`+`setuptools-scm`; `setuptools-scm` already landed in Phase 4 and `.env` is deferred, so pure pydantic + filters move is lighter on paper but the caller-update fan-out (4 sources + cli + deepdive + app.py) eats most of the wall clock.
- Critical path: `AppConfig` schema fits the real `config.yaml` without surprises — catch this early by parsing `config.example.yaml` before wiring any callers.
- Secondary path: `Source.fetch(cfg: AppConfig)` signature change — the `SOURCES` registry keeps working because keys are still `"rss" | "hackernews" | "sec_edgar" | "gmail"`; just the per-source access pattern changes.
- Tag at end as `phase-5`.

## Prerequisites

- ✅ Phase 4: Typer CLI + `research/` subpackage + scm versioning (commit `49a8de7`, tag `phase-4`).
- ✅ `make ci` green at start.
- ✅ Working tree clean.
- New dep: `pydantic>=2.5`. Already resolves cleanly against the current lockfile tree (pydantic v2 is pure-Python-optional + `pydantic_core`; no transitive conflict with `streamlit`, `feedparser`, `typer`).

---

## 1. Files to change

| Path | Action | Notes |
|---|---|---|
| `startup_radar/config/__init__.py` | **create** | Re-exports `AppConfig`, `load_config`, `ConfigError` for ergonomic imports. |
| `startup_radar/config/schema.py` | **create** | All pydantic models. ~140 lines. See §2.1. |
| `startup_radar/config/loader.py` | **create** | `load_config(path) -> AppConfig` + `ConfigError`. ~40 lines. See §2.2. |
| `config_loader.py` | **delete** | After callers updated. |
| `startup_radar/filters.py` | **create** (moved) | Copy of `filters.py` retyped against `AppConfig`; delete local `_parse_amount_musd`. |
| `filters.py` | **delete** | After `cli.py` import updated. |
| `startup_radar/sources/base.py` | edit | `fetch(self, cfg: dict[str, Any]) -> list[Startup]` → `fetch(self, cfg: AppConfig) -> list[Startup]`. Docstring refs `cfg["sources"]` → `cfg.sources`. |
| `startup_radar/sources/rss.py` | edit | `rss_cfg = cfg.sources.rss`; iterate `rss_cfg.feeds` (list of `RSSFeed`); `feed.url`, `feed.name`. Drop `.get(...)` fallbacks — pydantic defaults handle those. |
| `startup_radar/sources/hackernews.py` | edit | `hn_cfg = cfg.sources.hackernews`; `hn_cfg.queries`, `hn_cfg.lookback_hours`. |
| `startup_radar/sources/sec_edgar.py` | edit | `edgar_cfg = cfg.sources.sec_edgar`; `edgar_cfg.lookback_days`, `edgar_cfg.industry_sic_codes or None` (Phase 5 chooses `None` for empty-list sentinel — see §3 note 2). |
| `startup_radar/sources/gmail.py` | edit | `gmail_cfg = cfg.sources.gmail`; `gmail_cfg.enabled`, `gmail_cfg.label`. |
| `startup_radar/sources/registry.py` | edit | No logic change — but the docstring references `cfg["sources"]` and gets updated. |
| `startup_radar/cli.py` | edit | `_pipeline()`: `cfg.output.sqlite.enabled`, `cfg.output.sqlite.path`, `cfg.sources` dict access (see §3 note 3), `cfg.output.google_sheets`. `from filters import StartupFilter` → `from startup_radar.filters import StartupFilter`. `from config_loader import load_config` → `from startup_radar.config import load_config`. |
| `startup_radar/research/deepdive.py` | edit | Swap ~12 `cfg.get("...")` chains to attribute access. `_score_company(info, cfg)` signature: `cfg: dict` → `cfg: AppConfig`; same for `_generate_docx`. Top-level `from config_loader import load_config` → `from startup_radar.config import load_config`. Preserve `print()` calls (CLI-user-visible tier per observability rule). |
| `app.py` | edit | 2 call sites: `app.py:27-28` `sqlite_path = cfg.output.sqlite.path if cfg.output.sqlite.enabled else None` (or similar minimal shape); `app.py:219` `cfg.user.name`. `from config_loader import load_config` → `from startup_radar.config import load_config`. **NO other changes** — Phase 11 owns the decomposition. |
| `pyproject.toml` | edit | Add `pydantic>=2.5` dep; add `startup_radar.config` to `packages`; drop `config_loader` + `filters` from `py-modules`; expand `[tool.mypy] files`. |
| `tests/config/__init__.py` | **create** | Empty. |
| `tests/config/test_schema.py` | **create** | See §2.4. ~80 lines. |
| `tests/test_filters.py` | **create** | See §2.5. ~60 lines. Replaces nothing — Phase 5 is net-new test coverage for filters. |
| `tests/test_smoke.py` | edit | Update the `load_config()` smoke test to import from `startup_radar.config` and assert on `AppConfig` attributes instead of dict keys. |
| `.claude/CLAUDE.md` | edit | Repo layout: drop `config_loader.py`, `filters.py` from root; add `startup_radar/config/` and `startup_radar/filters.py`. "Configuration: …validated by `config_loader.py`; pydantic schema lands Phase 7." → "validated by pydantic `AppConfig` in `startup_radar/config/` (Phase 5)." Invariants: `os.getenv()` rule now points at `startup_radar/config/` (and for Phase 13, eventually `secrets.py`). |
| `.claude/rules/sources.md` | edit | `def fetch(self, cfg: dict) -> list[Startup]` → `def fetch(self, cfg: AppConfig) -> list[Startup]`. `Read from cfg["sources"][self.enabled_key]` → `Read from the typed sub-model (e.g. cfg.sources.rss)`. |
| `.claude/rules/observability.md` | edit | `print()` allow-list is unchanged, but the `structlog` migration note now references the `startup_radar/config/` module as the pattern for typed injection. (Small prose tweak.) |
| `.claude/settings.json` | edit | Drop `Edit(config_loader.py)` from allow-list (file gone); drop `Edit(filters.py)` similarly. `Edit(startup_radar/**)` covers replacements. |
| `.claude/hooks/pre-commit-check.sh` | edit | `CONFIG_OK=$(… grep -Ev '^(config_loader\.py\|startup_radar/config/)' …)` → `CONFIG_OK=$(… grep -Ev '^(startup_radar/config/)' …)`. The `os.getenv` guard now allows only the pydantic config subpackage. |
| `.claude/agents/source-implementer/SKILL.md` | edit | Scaffold snippet: show `cfg: AppConfig` signature + typed attribute access; import note to pull from `startup_radar.config` + `startup_radar.parsing`. |
| `.claude/agents/filter-tuner/SKILL.md` | edit | `from filters import StartupFilter` → `from startup_radar.filters import StartupFilter`; dry-run snippet uses `load_config()` from `startup_radar.config`. |
| `.claude/skills/deepdive/SKILL.md` | edit | Any `config.yaml`-shape references get a pointer to `startup_radar/config/schema.py` as the source of truth. |
| `AGENTS.md` | edit | Update the "filters + config" entries in the commands / layout sections. |
| `README.md` | edit | Any reference to `config_loader.py` → `startup_radar/config/`; reaffirm `config.yaml` is the user-editable surface and the pydantic schema is the shape contract. |
| `docs/AUDIT_FINDINGS.md` | edit | §2 (Configuration & secrets) — mark the schema-validation portion as RESOLVED (Phase 5); note `.env` / credentials-relocation remain open for Phase 13. |
| `docs/PRODUCTION_REFACTOR_PLAN.md` | edit | §0a row 7 marked ✅ done; annotate that `.env` deferred to Phase 13. Update §3.3 to link `startup_radar/config/schema.py`. |
| `docs/plans/phase-5.md` | **create** | This document. |

### Files explicitly NOT to touch

- `connections.py`, `database.py`, `sinks/google_sheets.py` — none read config. Leave.
- `startup_radar/models.py`, `startup_radar/parsing/**` — no change.
- `startup_radar/research/deepdive.py` body below the `_score_company` / `_generate_docx` / `main()` read sites — regex and .docx layout stay identical. Only the `cfg.<x>` access pattern changes.
- `scheduling/*` templates — invoke `startup-radar run --scheduled`; no config-layer coupling.
- `.github/workflows/daily.yml` — unchanged.
- `.claude/hooks/session-init.sh`, `.claude/hooks/pre-bash.sh`, `.claude/hooks/post-edit.sh` — unchanged.
- `config.yaml` (user's actual config) — never edited by Claude per CLAUDE.md. The schema must accept whatever shape `config.example.yaml` has today.
- `config.example.yaml` — schema fits this file as-is. No reshaping.

---

## 2. New file shapes

### 2.1 `startup_radar/config/schema.py`

```python
"""Pydantic v2 schema for config.yaml. Single source of truth for config shape.

Every field has a default where the current YAML treats it as optional, so
`AppConfig()` without args is *not* valid (no user / targets / sources / output),
but `AppConfig.model_validate(config_example_dict)` succeeds.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

_STRICT = ConfigDict(extra="forbid", str_strip_whitespace=True)


class _Strict(BaseModel):
    model_config = _STRICT


# --- user + targets --------------------------------------------------------

class UserConfig(_Strict):
    name: str = ""
    background: str = ""


Stage = Literal[
    "pre-seed", "seed", "series-a", "series-b", "series-c", "series-d", "any"
]


class TargetsConfig(_Strict):
    roles: list[str] = Field(default_factory=list)
    seniority_exclusions: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    min_stage: Stage = "any"
    large_seed_threshold_musd: float = 50.0


# --- sources ---------------------------------------------------------------

class RSSFeed(_Strict):
    name: str
    url: HttpUrl


class RSSConfig(_Strict):
    enabled: bool = False
    feeds: list[RSSFeed] = Field(default_factory=list)


class HackerNewsConfig(_Strict):
    enabled: bool = False
    queries: list[str] = Field(default_factory=list)
    lookback_hours: int = 48


class SECEdgarConfig(_Strict):
    enabled: bool = False
    industry_sic_codes: list[str] = Field(default_factory=list)
    min_amount_musd: float = 5.0
    lookback_days: int = 7


class GmailSenderParser(_Strict):
    """Per-sender routing hook — stays loose-typed for the /setup skill."""

    model_config = ConfigDict(extra="allow")  # skill-generated parsers are opaque


class GmailConfig(_Strict):
    enabled: bool = False
    label: str = "Startup Funding"
    senders: dict[str, GmailSenderParser] = Field(default_factory=dict)


class SourcesConfig(_Strict):
    rss: RSSConfig = Field(default_factory=RSSConfig)
    hackernews: HackerNewsConfig = Field(default_factory=HackerNewsConfig)
    sec_edgar: SECEdgarConfig = Field(default_factory=SECEdgarConfig)
    gmail: GmailConfig = Field(default_factory=GmailConfig)


# --- output ---------------------------------------------------------------

class SQLiteConfig(_Strict):
    enabled: bool = True
    path: str = "startup_radar.db"


class GoogleSheetsConfig(_Strict):
    enabled: bool = False
    sheet_id: str = ""


class OutputConfig(_Strict):
    sqlite: SQLiteConfig = Field(default_factory=SQLiteConfig)
    google_sheets: GoogleSheetsConfig = Field(default_factory=GoogleSheetsConfig)


# --- connections + deepdive -----------------------------------------------

class ConnectionsConfig(_Strict):
    enabled: bool = False
    csv_path: str = ""


FitWeight = Literal["high", "medium", "low"]


class FitFactors(_Strict):
    industry_match: FitWeight = "high"
    funding_stage: FitWeight = "high"
    location: FitWeight = "high"
    role_fit_signals: FitWeight = "high"
    founder_pedigree: FitWeight = "medium"
    vc_tier: FitWeight = "medium"


class Thresholds(_Strict):
    strong: float = 7.5
    moderate: float = 5.0


class DeepDiveConfig(_Strict):
    fit_factors: FitFactors = Field(default_factory=FitFactors)
    tier1_vcs: list[str] = Field(default_factory=list)
    thresholds: Thresholds = Field(default_factory=Thresholds)


# --- root ------------------------------------------------------------------

class AppConfig(_Strict):
    user: UserConfig
    targets: TargetsConfig
    sources: SourcesConfig
    output: OutputConfig
    connections: ConnectionsConfig = Field(default_factory=ConnectionsConfig)
    deepdive: DeepDiveConfig = Field(default_factory=DeepDiveConfig)
```

Notes on the schema:
- `extra="forbid"` at the root model and every sub-model catches YAML typos (e.g. `sourcs:`) with a clear error pointing at the offending field. `GmailSenderParser` is the single exception — the `/setup` skill generates arbitrary per-newsletter keys and forbidding extras would break it.
- `HttpUrl` on RSS feed URLs gets scheme+host validation for free.
- `industry_sic_codes` stays `list[str]` — the SEC EDGAR API takes them comma-joined; type-preserving either way.
- Four sub-models (`user`, `targets`, `sources`, `output`) are required, matching `config_loader._validate`'s 4-key check. `connections` and `deepdive` are optional with full-default sub-models (the `config.example.yaml` always includes them but absence is non-fatal).

### 2.2 `startup_radar/config/loader.py`

```python
"""Load and validate config.yaml → AppConfig."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from startup_radar.config.schema import AppConfig

BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_FILE = BASE_DIR / "config.yaml"
EXAMPLE_FILE = BASE_DIR / "config.example.yaml"


class ConfigError(Exception):
    """Raised when config.yaml is missing, unparseable, or fails schema validation."""


def load_config(path: Path | None = None) -> AppConfig:
    """Load config.yaml, falling back to config.example.yaml for first runs.

    Returns a fully-typed AppConfig. Wraps pydantic ValidationError in a
    ConfigError whose message points at field paths.
    """
    if path is not None:
        src = path
    else:
        src = CONFIG_FILE if CONFIG_FILE.exists() else EXAMPLE_FILE

    if not src.exists():
        raise ConfigError(
            "No config.yaml or config.example.yaml found. "
            "Run `claude` and invoke the /setup skill, or copy config.example.yaml to config.yaml."
        )

    try:
        with open(src, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"{src} is not valid YAML: {e}") from e

    try:
        return AppConfig.model_validate(raw)
    except ValidationError as e:
        # Format: "targets.min_stage: Input should be 'pre-seed', 'seed', ..."
        lines = [f"  {'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()]
        raise ConfigError(f"{src} failed validation:\n" + "\n".join(lines)) from e
```

### 2.3 `startup_radar/config/__init__.py`

```python
"""Config package — pydantic schema + loader. Single source of truth for config.yaml shape."""

from startup_radar.config.loader import ConfigError, load_config
from startup_radar.config.schema import (
    AppConfig,
    ConnectionsConfig,
    DeepDiveConfig,
    OutputConfig,
    SourcesConfig,
    TargetsConfig,
    UserConfig,
)

__all__ = [
    "AppConfig",
    "ConfigError",
    "ConnectionsConfig",
    "DeepDiveConfig",
    "OutputConfig",
    "SourcesConfig",
    "TargetsConfig",
    "UserConfig",
    "load_config",
]
```

### 2.4 `tests/config/test_schema.py`

```python
"""Pydantic schema unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from startup_radar.config import AppConfig, ConfigError, load_config

EXAMPLE = Path(__file__).resolve().parents[2] / "config.example.yaml"


def _example() -> dict:
    with open(EXAMPLE, encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_example_config_parses() -> None:
    cfg = AppConfig.model_validate(_example())
    assert cfg.targets.min_stage == "series-a"
    assert cfg.sources.rss.enabled is True
    assert cfg.output.sqlite.path == "startup_radar.db"


def test_missing_required_section_fails() -> None:
    raw = _example()
    del raw["targets"]
    with pytest.raises(Exception):  # pydantic.ValidationError
        AppConfig.model_validate(raw)


def test_unknown_top_level_key_fails() -> None:
    raw = _example()
    raw["sourcs"] = {}  # typo — extra="forbid" at root should reject it
    with pytest.raises(Exception):
        AppConfig.model_validate(raw)


def test_invalid_stage_fails() -> None:
    raw = _example()
    raw["targets"]["min_stage"] = "series-zzz"
    with pytest.raises(Exception):
        AppConfig.model_validate(raw)


def test_sic_codes_accepts_empty_list() -> None:
    raw = _example()
    raw["sources"]["sec_edgar"]["industry_sic_codes"] = []
    cfg = AppConfig.model_validate(raw)
    assert cfg.sources.sec_edgar.industry_sic_codes == []


def test_loader_wraps_validation_error(tmp_path: Path) -> None:
    bad = tmp_path / "config.yaml"
    bad.write_text("user:\n  name: x\n")  # missing targets / sources / output
    with pytest.raises(ConfigError) as exc:
        load_config(bad)
    # error message includes at least one field path
    assert "targets" in str(exc.value) or "sources" in str(exc.value)


def test_loader_yaml_error(tmp_path: Path) -> None:
    bad = tmp_path / "config.yaml"
    bad.write_text("::: not yaml :::")
    with pytest.raises(ConfigError):
        load_config(bad)
```

### 2.5 `tests/test_filters.py`

```python
"""Filter smoke tests. Also regression-guards the parse_amount_musd wire-in."""

from __future__ import annotations

from pathlib import Path

import yaml

from startup_radar.config import AppConfig
from startup_radar.filters import StartupFilter
from startup_radar.models import Startup

EXAMPLE = Path(__file__).resolve().parent.parent / "config.example.yaml"


def _cfg() -> AppConfig:
    with open(EXAMPLE, encoding="utf-8") as f:
        return AppConfig.model_validate(yaml.safe_load(f))


def test_series_a_passes() -> None:
    cfg = _cfg()
    f = StartupFilter(cfg)
    s = Startup(
        company_name="Anthropic",
        description="AI safety lab",
        funding_stage="Series A",
        amount_raised="$50M",
        location="San Francisco",
    )
    assert f.passes(s)


def test_seed_below_threshold_filtered_out() -> None:
    cfg = _cfg()  # min_stage=series-a, large_seed_threshold=50
    f = StartupFilter(cfg)
    s = Startup(
        company_name="Tiny AI",
        description="AI tool",
        funding_stage="Seed",
        amount_raised="$5M",
        location="Remote",
    )
    assert not f.passes(s)


def test_large_seed_passes_despite_min_stage() -> None:
    """Regression guard: parse_amount_musd from parsing.funding returns 60.0 for '$60M'."""
    cfg = _cfg()
    f = StartupFilter(cfg)
    s = Startup(
        company_name="Big Seed Co",
        description="AI infra",
        funding_stage="Seed",
        amount_raised="$60M",
        location="New York",
    )
    assert f.passes(s)


def test_industry_miss_filtered() -> None:
    cfg = _cfg()
    f = StartupFilter(cfg)
    s = Startup(
        company_name="Meatpackers Inc",
        description="Wholesale meat distribution",
        funding_stage="Series A",
        amount_raised="$20M",
        location="Kansas City",
    )
    assert not f.passes(s)
```

### 2.6 `startup_radar/filters.py` (moved, retyped)

Body shape:

```python
"""Config-driven filters for startups and jobs."""

from __future__ import annotations

import re

from startup_radar.config import AppConfig
from startup_radar.models import JobMatch, Startup
from startup_radar.parsing.funding import parse_amount_musd

_STAGE_ORDER = { ... }  # unchanged


def _stage_rank(stage: str) -> int:  # unchanged
    ...


class StartupFilter:
    def __init__(self, cfg: AppConfig) -> None:
        t = cfg.targets
        self.locations = [loc.lower() for loc in t.locations]
        self.industries = [ind.lower() for ind in t.industries]
        self.min_stage = t.min_stage.lower()
        self.min_stage_rank = _stage_rank(self.min_stage) if self.min_stage != "any" else -1
        self.large_seed_threshold = float(t.large_seed_threshold_musd)
        self._ind_patterns = [re.compile(r"\b" + re.escape(k) + r"\b") for k in self.industries]

    def passes(self, s: Startup) -> bool:  # unchanged body
        ...

    def filter(self, startups: list[Startup]) -> list[Startup]:  # unchanged
        ...

    def _stage_ok(self, stage: str, amount: str) -> bool:
        if self.min_stage == "any" or not stage:
            return True
        rank = _stage_rank(stage)
        if rank < 0:
            return True
        if rank >= self.min_stage_rank:
            return True
        musd = parse_amount_musd(amount) or 0.0
        if rank == 1 and musd >= self.large_seed_threshold:
            return True
        return False

    # _location_ok / _industry_ok unchanged


class JobFilter:
    def __init__(self, cfg: AppConfig) -> None:
        t = cfg.targets
        self.roles = [r.lower() for r in t.roles]
        self.exclusions = [e.lower() for e in t.seniority_exclusions]
        self.locations = [loc.lower() for loc in t.locations]
    # remainder unchanged
```

The local `_parse_amount_musd` (lines 35-44 of current `filters.py`) is deleted. `parse_amount_musd` returns `float | None`; we coalesce to `0.0` for the comparison. Behavior is identical: current code returns `0.0` for unparseable; new code returns `None`, coalesced to `0.0` at the call site.

### 2.7 `startup_radar/sources/base.py` diff

```diff
 from abc import ABC, abstractmethod
-from typing import Any

 from startup_radar.models import Startup
+from startup_radar.config import AppConfig


 class Source(ABC):
     """Pluggable data source.

     Subclasses MUST set `name` (human-readable) and `enabled_key`
-    (key inside cfg["sources"]). `fetch(cfg)` is the only required
-    method; `healthcheck()` is optional and returns True by default
-    (Phase 6's `startup-radar doctor` will use it).
+    (attribute name on cfg.sources). `fetch(cfg)` is the only required
+    method; `healthcheck()` is optional and returns True by default
+    (Phase 8's `startup-radar doctor` will use it).
     """

     name: str
     enabled_key: str

     @abstractmethod
-    def fetch(self, cfg: dict[str, Any]) -> list[Startup]:
+    def fetch(self, cfg: AppConfig) -> list[Startup]:
```

### 2.8 Representative source diff (`rss.py`)

```diff
-    def fetch(self, cfg: dict[str, Any]) -> list[Startup]:
-        rss_cfg = cfg.get("sources", {}).get(self.enabled_key, {})
-        if not rss_cfg.get("enabled"):
+    def fetch(self, cfg: AppConfig) -> list[Startup]:
+        rss_cfg = cfg.sources.rss
+        if not rss_cfg.enabled:
             return []
         out: list[Startup] = []
-        for feed in rss_cfg.get("feeds", []):
+        for feed in rss_cfg.feeds:
             try:
-                out.extend(self._fetch_one(feed["url"], feed.get("name", feed["url"])))
+                out.extend(self._fetch_one(str(feed.url), feed.name))
             except Exception as e:
                 log.warning(
                     "source.fetch_failed",
-                    extra={"source": self.name, "feed": feed.get("name"), "err": str(e)},
+                    extra={"source": self.name, "feed": feed.name, "err": str(e)},
                 )
```

> Note the `str(feed.url)` cast — `feedparser.parse` expects `str`, and pydantic's `HttpUrl` is a string-subclass in v2 but coerces cleanly via `str()`.

Same shape applies to `hackernews.py`, `sec_edgar.py`, `gmail.py`.

### 2.9 `pyproject.toml` diff

```diff
 dependencies = [
     "pyyaml>=6.0",
     "requests>=2.31.0",
     "feedparser>=6.0.10",
     "beautifulsoup4>=4.12.0",
     "python-dateutil>=2.8.2",
     "pandas>=2.0.0",
     "streamlit>=1.30.0",
     "duckduckgo-search>=6.0.0",
     "python-docx>=1.1.0",
     "typer>=0.12",
+    "pydantic>=2.5",
 ]

 [tool.setuptools]
 packages = [
     "startup_radar",
     "startup_radar.sources",
     "startup_radar.parsing",
     "startup_radar.research",
+    "startup_radar.config",
 ]
 py-modules = [
     "app",
-    "database", "filters",
-    "config_loader", "connections",
+    "database",
+    "connections",
 ]

 [tool.mypy]
 python_version = "3.10"
 ignore_missing_imports = true
-files = ["startup_radar/models.py", "startup_radar/parsing"]
+files = [
+    "startup_radar/models.py",
+    "startup_radar/parsing",
+    "startup_radar/config",
+    "startup_radar/filters.py",
+]
```

### 2.10 `app.py` micro-diff

```diff
-from config_loader import load_config
+from startup_radar.config import load_config

 # …

     cfg = load_config()
-    sqlite_path = cfg.get("output", {}).get("sqlite", {}).get("path")
+    sqlite_path = cfg.output.sqlite.path if cfg.output.sqlite.enabled else None

 # …

-    user_name = cfg.get("user", {}).get("name", "")
+    user_name = cfg.user.name
```

Exactly 3 line edits inside the 1,299-line file. Phase 11 absorbs the rest.

---

## 3. Step-by-step execution

### 3.1 Pre-flight

```bash
git status                               # clean
git log -1 --format='%h %s'              # 49a8de7 feat(cli):...
git tag --list 'phase-*'                 # phase-0..4
make ci                                  # green
```

### 3.2 Add the dep + scaffold the package

```bash
uv add 'pydantic>=2.5'
mkdir -p startup_radar/config tests/config
```

Parallel `Write` calls:
- `startup_radar/config/__init__.py` (§2.3)
- `startup_radar/config/schema.py` (§2.1)
- `startup_radar/config/loader.py` (§2.2)
- `tests/config/__init__.py` (empty)
- `tests/config/test_schema.py` (§2.4)

Smoke:
```bash
uv run python -c "from startup_radar.config import load_config; cfg = load_config(); print(type(cfg).__name__, cfg.targets.min_stage)"
# expect: AppConfig series-a   (or whatever the real config.yaml has)
uv run pytest tests/config -xvs
```

### 3.3 Move `filters.py`

```bash
git mv filters.py startup_radar/filters.py
```

Edit `startup_radar/filters.py` per §2.6. Add `tests/test_filters.py` per §2.5.

Smoke:
```bash
uv run pytest tests/test_filters.py -xvs
```

### 3.4 Retype the Source ABC + 4 sources

Parallel `Edit` calls:
- `startup_radar/sources/base.py` (§2.7)
- `startup_radar/sources/rss.py` (§2.8 pattern)
- `startup_radar/sources/hackernews.py` (§2.8 pattern; `cfg.sources.hackernews.queries`, `.lookback_hours`)
- `startup_radar/sources/sec_edgar.py` (§2.8 pattern; `cfg.sources.sec_edgar.lookback_days`, `.industry_sic_codes or None`)
- `startup_radar/sources/gmail.py` (§2.8 pattern; `cfg.sources.gmail.label`)
- `startup_radar/sources/registry.py` (docstring update only)

Smoke:
```bash
uv run python -c "
from startup_radar.config import load_config
from startup_radar.sources.registry import SOURCES
cfg = load_config()
for key, s in SOURCES.items():
    print(key, type(s).__name__, len(s.fetch(cfg)) if False else 'ok')  # don't actually fetch
"
```

### 3.5 Update `cli.py` / `deepdive.py` / `app.py`

Parallel `Edit` calls (three separate files, no conflict risk):
- `startup_radar/cli.py::_pipeline` — attribute access + import swap.
- `startup_radar/research/deepdive.py` — ~12 attribute-access swaps in `_score_company` and `_generate_docx` + `main()` + the top-level import.
- `app.py` — 3 edits per §2.10.

Smoke end-to-end:
```bash
uv run startup-radar run                      # pipeline on the real config
uv run startup-radar deepdive "Anthropic"     # generates .docx (respects reports/ cwd)
uv run startup-radar serve --port 8503 &      # dashboard boots; ctrl-c after 2s
```

### 3.6 Delete old roots

```bash
git rm config_loader.py
# filters.py was already git mv'd in 3.3
```

### 3.7 Update `pyproject.toml` + resync

Apply §2.9 via `Edit`. Then:
```bash
uv sync --all-extras
uv run startup-radar --help                   # still works
```

### 3.8 Update `tests/test_smoke.py`

Swap `from config_loader import load_config` → `from startup_radar.config import load_config`, and assert on `cfg.targets.min_stage` instead of `cfg["targets"]["min_stage"]`.

### 3.9 Full local CI

```bash
make ci                                       # ruff + format + mypy + pytest
# test count: smoke(≥4) + parsing.funding + parsing.normalize + config(≥7) + filters(≥4) ≈ 16+
```

Any red: STOP. See §5 risks.

### 3.10 Update harness + docs

Parallel `Edit` calls per §1 "Files to change":
- `.claude/CLAUDE.md`, `.claude/rules/sources.md`, `.claude/rules/observability.md`, `.claude/settings.json`, `.claude/hooks/pre-commit-check.sh`
- `.claude/agents/source-implementer/SKILL.md`, `.claude/agents/filter-tuner/SKILL.md`, `.claude/skills/deepdive/SKILL.md`
- `AGENTS.md`, `README.md`
- `docs/AUDIT_FINDINGS.md` §2 → RESOLVED (Phase 5); flag `.env` / credentials relocation as still-open for Phase 13
- `docs/PRODUCTION_REFACTOR_PLAN.md` §0a row 7 → ✅ done + note `.env` deferred

### 3.11 Ship

Use `/ship`. Suggested commit message:

```
feat(config): pydantic AppConfig + filters move

Replaces config_loader.py's 4-key-existence check with a pydantic v2
schema rooted in startup_radar/config/{schema,loader}.py. Validation
errors now point at field paths (e.g. "targets.min_stage: Input should
be 'pre-seed', 'seed', ..."). extra="forbid" catches YAML typos.

Moves filters.py into the package as startup_radar/filters.py and
retypes StartupFilter / JobFilter constructors against AppConfig.
Wires parse_amount_musd from parsing.funding, retiring the duplicate
_parse_amount_musd in filters.

Retypes Source.fetch(cfg) from dict[str, Any] to AppConfig; all four
sources (rss, hackernews, sec_edgar, gmail) now read typed sub-models
(cfg.sources.rss.feeds, etc.). cli._pipeline, deepdive._score_company
and app.py swap to attribute access — dashboard body untouched, still
Phase 11.

mypy scope expanded to startup_radar/config and startup_radar/filters.py.

Closes docs/AUDIT_FINDINGS.md §2 (schema validation). Defers .env /
pydantic-settings to Phase 13 (no current env-var consumer; structlog
+ Sentry are the natural first tenants).
```

Then tag: `STARTUP_RADAR_SHIP=1 git tag phase-5`.

---

## 4. Verification checklist

Between 3.9 and 3.11, confirm each:

```bash
uv run python -c "from startup_radar.config import AppConfig, load_config; print(load_config().targets.min_stage)"
uv run python -c "from startup_radar.filters import StartupFilter; print(StartupFilter)"
uv run python -c "from startup_radar.sources.registry import SOURCES; print(sorted(SOURCES))"
uv run startup-radar run                                  # pipeline still lands rows
uv run startup-radar deepdive "Anthropic"                 # .docx still generated
make ci                                                   # green, ≥16 tests

# Grep checks
git grep -nE 'from config_loader' -- ':!docs/' ':!docs/plans/'
# expect: zero matches
git grep -nE 'from filters import'
# expect: zero matches (all callers now use startup_radar.filters)
git grep -nE 'cfg\.get\("(user|targets|sources|output|connections|deepdive)"' -- 'startup_radar/' 'app.py'
# expect: zero matches — all attribute access after Phase 5
test ! -f config_loader.py && test ! -f filters.py && echo "roots deleted"
```

---

## 5. Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| 1 | Real user `config.yaml` has keys the schema rejects under `extra="forbid"` | Medium | `startup-radar run` crashes on start with a "validation failed" | Run `AppConfig.model_validate(yaml.safe_load(open("config.yaml")))` locally before merging. If a new key IS legitimate, add it to `schema.py`. Users with heavily-customized configs get a clear `ConfigError` pointing at the unknown field — they add it to the schema PR or remove from YAML. |
| 2 | `HttpUrl` rejects one of the default RSS feed URLs (e.g. a feed with a weird path) | Low | First-run crash | Fallback: change `url: HttpUrl` → `url: str` if the example feeds don't all validate. Mitigate early by running `AppConfig.model_validate(_example())` in 3.2 before wiring callers. |
| 3 | `pydantic` v2 pulls `pydantic_core` binary wheels that conflict with a pinned `pandas` wheel under `uv` | Low | `uv sync` fails | Both are independent pure/binary deps. pydantic v2.5+ and pandas 2+ have been co-installed in thousands of projects. If conflict: drop `pydantic>=2.5` → `pydantic>=2.4`. |
| 4 | `Source.fetch(cfg: AppConfig)` signature change breaks the existing `.claude/agents/source-implementer/SKILL.md` scaffold until the doc is updated | Certain | Future agent invocations generate dict-typed sources | `.claude/agents/source-implementer/SKILL.md` update is in §1 / 3.10. |
| 5 | Streamlit caches the un-hashable `AppConfig` instance if any `@st.cache_data` wraps a function that takes `cfg` | Low | `TypeError: object of type 'AppConfig' is not hashable` | `app.py`'s existing `@st.cache_data` decorators don't take `cfg` as an arg — they take DB-read primitives. Grep `git grep -nE '@st\.cache_data' app.py` before ship; if any cache-wrapped fn takes `cfg`, prefix the arg with `_cfg` to skip hashing, or pass `cfg.model_dump()`. |
| 6 | `_parse_amount_musd` → `parse_amount_musd` behavior divergence in the large-seed-threshold path | Low | Regression: seed rounds with huge amounts get filtered out | Regression test `test_large_seed_passes_despite_min_stage` in §2.5 pins this. Current code: `_parse_amount_musd("$60M") -> 60.0`. New code: `parse_amount_musd("$60M") -> 60.0`, coalesced from `None` path identically. |
| 7 | `deepdive.py` has a 4th access chain I missed when swapping to attribute access | Medium | `AttributeError` at `deepdive` runtime | 3.5 includes `uv run startup-radar deepdive "Anthropic"` smoke. Also: `git grep -nE 'cfg\.get\("'` scoped to `startup_radar/research/deepdive.py` before commit should return 0. |
| 8 | `[tool.mypy] files` expansion trips on one of the new modules because of `pydantic` plugin requirements | Medium | mypy red | Add `plugins = ["pydantic.mypy"]` to `[tool.mypy]` in §2.9 if needed. Pydantic v2's mypy plugin is optional — stock mypy handles most cases; the plugin helps with custom validators. Phase 5 has none, so stock should pass. |
| 9 | `config.example.yaml` drifts from `schema.py` over time (Phase 7 wizard writes YAML shapes that the schema doesn't know about) | Low | First-run crash for fresh installs | `tests/config/test_schema.py::test_example_config_parses` catches drift in CI. |
| 10 | `str(HttpUrl)` in `rss.py` ends up with a trailing `/` that `feedparser` dislikes (pydantic normalizes URLs) | Low | RSS fetch returns fewer rows for feeds that are sensitive to trailing slashes | Unlikely — `feedparser` is tolerant. If observed: strip trailing `/` from `str(feed.url)` at the call site. |
| 11 | `extra="allow"` on `GmailSenderParser` lets the schema accept malformed per-newsletter config without any error | Certain | Acceptable — same as today | The `/setup` skill owns per-sender parser shape. Phase 5 doesn't regress — today there's no validation either. Phase 12 or a dedicated skill rework can tighten. |
| 12 | Dropping `filters` from `[tool.setuptools] py-modules` without also removing the `filters.py` file first causes setuptools to complain | Certain | `uv sync` errors | Order in 3.3 is: `git mv filters.py startup_radar/filters.py` FIRST, then edit `pyproject.toml` in 3.7. Following the sequence prevents the half-state. |
| 13 | `tests/test_smoke.py` currently asserts on dict-shaped cfg; tests/config/test_schema.py is additive | Certain | Cosmetic test collision — both test similar things | 3.8 explicitly updates the smoke test. |

---

## 6. Done criteria

- [ ] `startup_radar/config/{__init__.py, schema.py, loader.py}` exist; `AppConfig.model_validate(example_dict)` returns a populated instance.
- [ ] `startup_radar/filters.py` exists; `StartupFilter(AppConfig(...))` works; `filters.py` at root is deleted.
- [ ] `config_loader.py` at root is deleted.
- [ ] `Source.fetch(self, cfg: AppConfig) -> list[Startup]` in the ABC; all 4 sources use typed attribute access; registry unchanged.
- [ ] `cli._pipeline`, `research/deepdive.py`, `app.py` all read typed attributes; no `cfg.get("user"|"targets"|"sources"|"output"|"connections"|"deepdive")` remains in `startup_radar/` or `app.py`.
- [ ] `pyproject.toml` declares `pydantic>=2.5`, adds `startup_radar.config` to `packages`, drops `config_loader` + `filters` from `py-modules`, expands mypy `files`.
- [ ] `uv sync --all-extras` succeeds end-to-end.
- [ ] `make ci` passes with ≥16 tests (smoke + parsing.funding + parsing.normalize + config ≥7 + filters ≥4).
- [ ] `startup-radar run` reaches "Total extracted: N" end-to-end against a real `config.yaml`.
- [ ] `startup-radar deepdive "Anthropic"` generates a .docx.
- [ ] `.claude/CLAUDE.md`, `.claude/rules/sources.md`, `.claude/rules/observability.md`, `.claude/settings.json`, `.claude/hooks/pre-commit-check.sh`, `.claude/agents/{source-implementer,filter-tuner}/SKILL.md`, `.claude/skills/deepdive/SKILL.md` all updated.
- [ ] `AGENTS.md`, `README.md` updated.
- [ ] `docs/AUDIT_FINDINGS.md` §2 → RESOLVED (Phase 5) (schema-validation portion); credentials relocation + .env still open for Phase 13.
- [ ] `docs/PRODUCTION_REFACTOR_PLAN.md` §0a row 7 → ✅ done + `.env` deferred note.
- [ ] `docs/plans/phase-5.md` (this file) present.
- [ ] Commit tagged `phase-5`.

---

## 7. What this enables

- **Phase 7 (`startup-radar init` wizard):** wizard builds an `AppConfig`, calls `AppConfig.model_dump(mode="yaml")` (or `yaml.dump(cfg.model_dump())`), writes to `config.yaml`. Schema-round-tripping means the wizard cannot produce a config that fails validation.
- **Phase 8 (`doctor` / `status` / `backup`):** `doctor` calls `AppConfig.model_validate()` and catches `ConfigError`. No re-implementation of validation.
- **Phase 12 (Storage class):** `Storage(cfg.output.sqlite.path)` — typed, one-liner. `STARTUP_RADAR_DB_URL` support sits naturally alongside `OutputConfig`.
- **Phase 13 (structlog + retries + `.env`):** `Secrets(BaseSettings)` in `startup_radar/config/secrets.py` slots in next to `schema.py`. `AppConfig` optionally gains a `secrets: Secrets = Field(default_factory=Secrets)` field, or `Secrets` stays decoupled and lives in a separate global. Phase 5's package layout is the home either way.
- **Phase 10 (vcrpy fixtures):** each source's test can `AppConfig.model_validate({...})` a minimal fixture config — typed, no dict-literal boilerplate.
- **Phase 11 (dashboard split):** each extracted `web/pages/N_*.py` takes the shared `cfg: AppConfig` via session-state. Type-safe across page boundaries.
