"""Source ABC. Every data source subclasses this and registers itself in registry.py."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from startup_radar.models import Startup


class Source(ABC):
    """Pluggable data source.

    Subclasses MUST set `name` (human-readable) and `enabled_key`
    (key inside cfg["sources"]). `fetch(cfg)` is the only required
    method; `healthcheck()` is optional and returns True by default
    (Phase 6's `startup-radar doctor` will use it).
    """

    name: str
    enabled_key: str

    @abstractmethod
    def fetch(self, cfg: dict[str, Any]) -> list[Startup]:
        """Pull records and return zero or more Startup rows.

        On failure, log at WARNING and return []. Never raise out of
        this method — the orchestrator should never see a partial
        crash that aborts the whole run.
        """

    def healthcheck(self) -> bool:
        return True
