"""Phase 0 smoke tests — placeholder so `make test` exits 0.

Real coverage lands in Phase 10 (vcrpy fixtures + per-source tests).
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def test_models_importable() -> None:
    from startup_radar.models import JobMatch, Startup  # noqa: F401


def test_dedup_strips_legal_suffixes() -> None:
    """Phase 0 #2: 'OpenAI' and 'Open AI Inc.' must dedupe to the same key."""
    from startup_radar.parsing.normalize import normalize_company

    assert normalize_company("OpenAI") == normalize_company("Open AI Inc.")
    assert normalize_company("Acme Corp") == normalize_company("acme")
    assert normalize_company("WeWork") == normalize_company("We Work")
    assert normalize_company("Foo Labs LLC") == normalize_company("Foo")


def test_oauth_scopes_unified() -> None:
    """Phase 0 #3: Gmail and Sheets must share the same SCOPES list."""
    from sinks.google_sheets import SCOPES as sheets_scopes
    from startup_radar.sources.gmail import SCOPES as gmail_scopes

    assert set(gmail_scopes) == set(sheets_scopes)
    assert "https://www.googleapis.com/auth/gmail.readonly" in gmail_scopes
    assert "https://www.googleapis.com/auth/spreadsheets" in gmail_scopes


def test_registry_has_all_sources() -> None:
    """Phase 3: Source ABC + registry. Every built-in source self-registers."""
    from startup_radar.sources.registry import SOURCES

    assert set(SOURCES.keys()) >= {"rss", "hackernews", "sec_edgar"}


def test_config_loads_as_appconfig() -> None:
    """Phase 5: load_config returns a typed AppConfig."""
    from startup_radar.config import AppConfig, load_config

    cfg = load_config()
    assert isinstance(cfg, AppConfig)
    assert cfg.targets.min_stage == "series-a"
