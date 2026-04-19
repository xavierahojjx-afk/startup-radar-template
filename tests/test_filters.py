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
    cfg = _cfg()
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
