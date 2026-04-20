"""Unit tests for the shared httpx.Client singleton."""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import yaml

from startup_radar import http as http_module
from startup_radar.config import AppConfig

EXAMPLE = Path(__file__).resolve().parents[2] / "config.example.yaml"


def _cfg(timeout: float = 10.0) -> AppConfig:
    with open(EXAMPLE, encoding="utf-8") as f:
        cfg = AppConfig.model_validate(yaml.safe_load(f))
    cfg.network.timeout_seconds = timeout
    return cfg


def test_get_client_returns_same_instance_for_same_timeout() -> None:
    cfg = _cfg(timeout=10.0)
    a = http_module.get_client(cfg)
    b = http_module.get_client(cfg)
    assert a is b
    assert isinstance(a, httpx.Client)


def test_get_client_applies_timeout_from_cfg() -> None:
    cfg = _cfg(timeout=7.5)
    client = http_module.get_client(cfg)
    # httpx.Timeout exposes `.read` (and connect/write/pool) — all default to cfg value
    assert client.timeout.read == pytest.approx(7.5)


def test_get_client_sets_default_user_agent() -> None:
    cfg = _cfg()
    client = http_module.get_client(cfg)
    ua = client.headers.get("User-Agent", "")
    assert "startup-radar/" in ua


def test_cache_clear_forces_new_instance() -> None:
    cfg = _cfg()
    a = http_module.get_client(cfg)
    http_module.get_client.cache_clear()  # type: ignore[attr-defined]
    b = http_module.get_client(cfg)
    assert a is not b
