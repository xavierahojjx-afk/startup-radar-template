"""Hacker News source — Algolia search API.

Free, no auth. Use it to fish for "raised Series X" threads.
"""

import re
from datetime import datetime, timedelta
from typing import Iterable

import requests

from models import Startup

ALGOLIA_URL = "https://hn.algolia.com/api/v1/search_by_date"

_AMOUNT_RE = re.compile(r"\$\s*[\d,.]+\s*(?:B|M|billion|million)\b", re.IGNORECASE)
_STAGE_RE = re.compile(r"\b(Pre-?Seed|Seed|Series\s+[A-F]\d?\+?)\b", re.IGNORECASE)
_COMPANY_RE = re.compile(
    r"^([A-Z][\w\-.&' ]{1,40}?)(?:\s+raises|\s+raised|\s+secures|\s+closes|\s+nabs)",
    re.IGNORECASE,
)


def fetch(queries: Iterable[str], lookback_hours: int = 48) -> list[Startup]:
    cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)
    cutoff_ts = int(cutoff.timestamp())

    seen_titles: set[str] = set()
    results: list[Startup] = []

    for query in queries:
        try:
            resp = requests.get(
                ALGOLIA_URL,
                params={
                    "query": query,
                    "tags": "story",
                    "numericFilters": f"created_at_i>{cutoff_ts}",
                    "hitsPerPage": 50,
                },
                timeout=15,
            )
            resp.raise_for_status()
            hits = resp.json().get("hits", [])
        except Exception as e:
            print(f"  HN error ({query}): {e}")
            continue

        for hit in hits:
            title = hit.get("title") or ""
            if not title or title in seen_titles:
                continue
            seen_titles.add(title)

            m = _COMPANY_RE.match(title)
            if not m:
                continue

            amount = _AMOUNT_RE.search(title)
            stage = _STAGE_RE.search(title)

            created_at = hit.get("created_at") or ""
            date_found = None
            if created_at:
                try:
                    date_found = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                except Exception:
                    pass

            results.append(Startup(
                company_name=m.group(1).strip(),
                description=title,
                funding_stage=stage.group(0) if stage else "",
                amount_raised=amount.group(0) if amount else "",
                source="Hacker News",
                source_url=hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                date_found=date_found,
            ))

    return results
