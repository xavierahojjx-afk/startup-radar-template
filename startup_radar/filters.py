"""Config-driven filters for startups and jobs."""

from __future__ import annotations

import re

from startup_radar.config import AppConfig
from startup_radar.models import JobMatch, Startup
from startup_radar.parsing.funding import parse_amount_musd

_STAGE_ORDER = {
    "pre-seed": 0,
    "preseed": 0,
    "seed": 1,
    "series-a": 2,
    "series a": 2,
    "series-b": 3,
    "series b": 3,
    "series-c": 4,
    "series c": 4,
    "series-d": 5,
    "series d": 5,
}


def _stage_rank(stage: str) -> int:
    if not stage:
        return -1
    s = stage.lower().strip()
    for key, rank in _STAGE_ORDER.items():
        if key in s:
            return rank
    m = re.search(r"series\s+([a-f])", s)
    if m:
        return 2 + (ord(m.group(1)) - ord("a"))
    return -1


class StartupFilter:
    def __init__(self, cfg: AppConfig) -> None:
        t = cfg.targets
        self.locations = [loc.lower() for loc in t.locations]
        self.industries = [ind.lower() for ind in t.industries]
        self.min_stage = t.min_stage.lower()
        self.min_stage_rank = _stage_rank(self.min_stage) if self.min_stage != "any" else -1
        self.large_seed_threshold = float(t.large_seed_threshold_musd)
        self._ind_patterns = [re.compile(r"\b" + re.escape(k) + r"\b") for k in self.industries]

    def passes(self, s: Startup) -> bool:
        return (
            self._stage_ok(s.funding_stage, s.amount_raised)
            and self._location_ok(s.location)
            and self._industry_ok(s)
        )

    def filter(self, startups: list[Startup]) -> list[Startup]:
        return [s for s in startups if self.passes(s)]

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

    def _location_ok(self, location: str) -> bool:
        if not self.locations:
            return True
        if not location:
            return False
        lower = location.lower()
        return any(loc in lower for loc in self.locations)

    def _industry_ok(self, s: Startup) -> bool:
        if not self._ind_patterns:
            return True
        text = f"{s.company_name} {s.description}".lower()
        return any(p.search(text) for p in self._ind_patterns)


class JobFilter:
    def __init__(self, cfg: AppConfig) -> None:
        t = cfg.targets
        self.roles = [r.lower() for r in t.roles]
        self.exclusions = [e.lower() for e in t.seniority_exclusions]
        self.locations = [loc.lower() for loc in t.locations]

    def role_matches(self, title: str) -> bool:
        if not title:
            return False
        t = title.lower()
        if any(ex in t for ex in self.exclusions):
            return False
        if not self.roles:
            return True
        return any(r in t for r in self.roles)

    def location_matches(self, location: str) -> bool:
        if not self.locations:
            return True
        if not location:
            return False
        lower = location.lower()
        if "remote" in lower:
            return True
        return any(loc in lower for loc in self.locations)

    def passes(self, j: JobMatch) -> bool:
        return self.role_matches(j.role_title) and self.location_matches(j.location)

    def filter(self, jobs: list[JobMatch]) -> list[JobMatch]:
        return [j for j in jobs if self.passes(j)]
