"""Shared pytest fixtures — Phase 6 `fake_repo` + Phase 8 vcr config."""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pytest

from startup_radar.config import secrets
from startup_radar.http import get_client
from startup_radar.observability.logging import configure_logging

REPO_ROOT = Path(__file__).resolve().parent.parent
CASSETTE_DIR = Path(__file__).resolve().parent / "fixtures" / "cassettes"


@pytest.fixture(autouse=True)
def _structlog_routes_through_stdlib() -> None:
    """Ensure structlog emits via the stdlib root logger so pytest's caplog
    sees records. Idempotent: our handler is sentinel-tagged so pytest's
    `LogCaptureHandler` stays attached."""
    configure_logging(json=False)


@pytest.fixture(autouse=True)
def _clear_secrets_cache() -> None:
    """Reset the lru-cached `Secrets` singleton between tests so monkeypatched
    env vars don't leak across test boundaries."""
    secrets.cache_clear()  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def _clear_http_client_cache() -> None:
    """Reset the shared httpx.Client cache between tests so per-test tweaks to
    `cfg.network.timeout_seconds` don't leak."""
    get_client.cache_clear()  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def _no_retry_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralize `sources._retry` backoff so tests that hit the retry path
    don't burn seven seconds each. Monkeypatches the module-local `_sleep`
    alias — replacing `time.sleep` here would clobber it process-wide."""
    monkeypatch.setattr("startup_radar.sources._retry._sleep", lambda _s: None)


@pytest.fixture(scope="session")
def vcr_config() -> dict:
    """Global vcrpy config. Scrubs identity/secret headers on record.

    CI=1 flips `record_mode` to `none` — a missing cassette fails the test
    loudly rather than silently hitting the network. Locally the default is
    `once`: record on first run, replay thereafter.
    """
    return {
        "filter_headers": [
            ("authorization", "REDACTED"),
            ("cookie", "REDACTED"),
            ("user-agent", "startup-radar-test"),
            ("x-api-key", "REDACTED"),
        ],
        "filter_query_parameters": [("key", "REDACTED"), ("api_key", "REDACTED")],
        "record_mode": "none" if os.environ.get("CI") else "once",
        "decode_compressed_response": True,
    }


@pytest.fixture
def vcr_cassette_dir(request: pytest.FixtureRequest) -> str:
    """One cassette subdir per source: tests/fixtures/cassettes/<source>/."""
    module = Path(request.node.fspath).stem
    source = module.replace("test_source_", "")
    return str(CASSETTE_DIR / source)


@pytest.fixture
def fake_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Tmp_path with a minimal (config.yaml, startup_radar.db, logs/) layout.

    Monkeypatches both `startup_radar.cli._repo_root` and the loader's
    `CONFIG_FILE` constant so all three Phase-6 helpers consistently see
    the tmp_path, not the real repo.
    """
    example = REPO_ROOT / "config.example.yaml"
    (tmp_path / "config.yaml").write_text(example.read_text(encoding="utf-8"))

    db = tmp_path / "startup_radar.db"
    with sqlite3.connect(str(db)) as conn:
        conn.executescript(
            """
            CREATE TABLE startups (id INTEGER PRIMARY KEY, company_name TEXT);
            CREATE TABLE job_matches (id INTEGER PRIMARY KEY, company_name TEXT);
            CREATE TABLE connections (id INTEGER PRIMARY KEY, company TEXT);
            """
        )

    (tmp_path / "logs").mkdir()

    monkeypatch.setattr("startup_radar.cli._repo_root", lambda: tmp_path)
    monkeypatch.setattr("startup_radar.config.loader.CONFIG_FILE", tmp_path / "config.yaml")
    return tmp_path
