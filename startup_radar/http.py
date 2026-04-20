"""Shared httpx.Client singleton for all outbound HTTP.

One client per process. Default ``timeout`` is sourced from
``cfg.network.timeout_seconds`` (Phase 11); default ``User-Agent`` is
``startup-radar/<version>``. Sources that need a per-request UA override
(EDGAR's compliance header) pass ``headers=`` on the call — httpx merges
per-request headers over client defaults.

Test seam: ``get_client.cache_clear()`` in ``tests/conftest.py`` runs between
tests so per-test ``cfg.network.timeout_seconds`` tweaks don't leak across
cases.
"""

from __future__ import annotations

from functools import lru_cache

import httpx

from startup_radar import __version__
from startup_radar.config import AppConfig

_DEFAULT_UA = (
    f"startup-radar/{__version__} (+https://github.com/xavierahojjx-afk/startup-radar-template)"
)


@lru_cache(maxsize=1)
def _client_for(timeout_seconds: float) -> httpx.Client:
    return httpx.Client(
        timeout=timeout_seconds,
        headers={"User-Agent": _DEFAULT_UA},
        follow_redirects=True,
    )


def get_client(cfg: AppConfig) -> httpx.Client:
    """Return the process-wide httpx.Client configured from ``cfg``."""
    return _client_for(float(cfg.network.timeout_seconds))


def cache_clear() -> None:
    """Drop every cached client. Called between tests; safe in prod too."""
    _client_for.cache_clear()


get_client.cache_clear = cache_clear  # type: ignore[attr-defined]
