"""Company-name normalization for dedup. Single source of truth."""

from __future__ import annotations

import re

LEGAL_SUFFIX_RE = re.compile(
    r"[\s,]+(inc|incorporated|llc|l\.l\.c|ltd|limited|corp|corporation|co|company|gmbh|sa|ag|plc|holdings|labs?|technologies|tech)\.?$",
    re.IGNORECASE,
)


def normalize_company(name: str) -> str:
    """Canonical key for dedup. 'Open AI Inc.' → 'openai'."""
    name = name.lower().strip()
    prev = None
    while prev != name:
        prev = name
        name = LEGAL_SUFFIX_RE.sub("", name).strip()
    return re.sub(r"[\s.\-&']+", "", name)


def dedup_key(name: str) -> str:
    """Alias kept for callers that read clearer with this name."""
    return normalize_company(name)
