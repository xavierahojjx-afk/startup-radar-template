"""Config-driven filters for startups and jobs."""

import re

from startup_radar.models import JobMatch, Startup

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


def _parse_amount_musd(amount: str) -> float:
    if not amount:
        return 0.0
    m = re.search(r"\$?\s*([\d,.]+)\s*(m|million|b|billion)", amount, re.IGNORECASE)
    if not m:
        return 0.0
    val = float(m.group(1).replace(",", ""))
    if m.group(2).lower().startswith("b"):
        val *= 1000
    return val


class StartupFilter:
    def __init__(self, cfg: dict):
        targets = cfg["targets"]
        self.locations = [loc.lower() for loc in targets.get("locations", [])]
        self.industries = [ind.lower() for ind in targets.get("industries", [])]
        self.min_stage = targets.get("min_stage", "any").lower()
        self.min_stage_rank = _stage_rank(self.min_stage) if self.min_stage != "any" else -1
        self.large_seed_threshold = float(targets.get("large_seed_threshold_musd", 50))
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
        if rank == 1 and _parse_amount_musd(amount) >= self.large_seed_threshold:
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
    def __init__(self, cfg: dict):
        targets = cfg["targets"]
        self.roles = [r.lower() for r in targets.get("roles", [])]
        self.exclusions = [e.lower() for e in targets.get("seniority_exclusions", [])]
        self.locations = [loc.lower() for loc in targets.get("locations", [])]

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
