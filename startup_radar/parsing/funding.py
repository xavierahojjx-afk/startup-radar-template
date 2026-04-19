"""Funding-announcement regex helpers. Single source of truth — DO NOT duplicate elsewhere."""

from __future__ import annotations

import re

AMOUNT_RE = re.compile(r"\$\s*[\d,.]+\s*(?:B|M|billion|million)\b", re.IGNORECASE)
STAGE_RE = re.compile(r"\b(Pre-?Seed|Seed(?:\s+Round)?|Series\s+[A-F]\d?\+?)\b", re.IGNORECASE)
COMPANY_SUBJECT_RE = re.compile(
    r"^([A-Z][\w\-.&' ]{1,40}?)(?:\s+raises|\s+secures|\s+closes|\s+lands|\s+nabs|\s+announces|\s+picks up)",
    re.IGNORECASE,
)
COMPANY_INLINE_RE = re.compile(
    r"\b([A-Z][\w\-.&']{1,40}?)\s+(?:raises|raised|secures|closes|nabs|announces)\s+",
    re.IGNORECASE,
)

_AMOUNT_PARSE_RE = re.compile(r"\$?\s*([\d,.]+)\s*(m|million|b|billion)", re.IGNORECASE)


def parse_amount_musd(amount: str | None) -> float | None:
    """Parse '$2.5M' / '$1B' / etc. into millions of USD. Returns None if unparseable."""
    if not amount:
        return None
    m = _AMOUNT_PARSE_RE.search(amount)
    if not m:
        return None
    val = float(m.group(1).replace(",", ""))
    if m.group(2).lower().startswith("b"):
        val *= 1000
    return val
