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


Stage = Literal["pre-seed", "seed", "series-a", "series-b", "series-c", "series-d", "any"]


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

    model_config = ConfigDict(extra="allow")


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
