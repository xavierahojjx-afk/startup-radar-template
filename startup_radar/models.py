"""Core data models shared across sources, filters, and sinks."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Startup:
    company_name: str
    description: str = ""
    funding_stage: str = ""
    amount_raised: str = ""
    location: str = ""
    website: str = ""
    source: str = ""
    source_url: str = ""
    date_found: datetime | None = None


@dataclass
class JobMatch:
    company_name: str
    company_description: str = ""
    role_title: str = ""
    location: str = ""
    url: str = ""
    priority: str = "Medium"
    source: str = ""
    date_found: datetime | None = None
