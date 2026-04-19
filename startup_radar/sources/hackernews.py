"""Hacker News source — Algolia search API.

Free, no auth. Use it to fish for "raised Series X" threads.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import requests

from startup_radar.config import AppConfig
from startup_radar.models import Startup
from startup_radar.parsing.funding import AMOUNT_RE, COMPANY_SUBJECT_RE, STAGE_RE
from startup_radar.sources.base import Source

ALGOLIA_URL = "https://hn.algolia.com/api/v1/search_by_date"

log = logging.getLogger(__name__)


class HackerNewsSource(Source):
    name = "Hacker News"
    enabled_key = "hackernews"

    def fetch(self, cfg: AppConfig) -> list[Startup]:
        hn_cfg = cfg.sources.hackernews
        if not hn_cfg.enabled:
            return []

        queries = hn_cfg.queries
        lookback_hours = int(hn_cfg.lookback_hours)
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
                log.warning(
                    "source.fetch_failed",
                    extra={"source": self.name, "query": query, "err": str(e)},
                )
                continue

            for hit in hits:
                title = hit.get("title") or ""
                if not title or title in seen_titles:
                    continue
                seen_titles.add(title)

                m = COMPANY_SUBJECT_RE.match(title)
                if not m:
                    continue

                amount = AMOUNT_RE.search(title)
                stage = STAGE_RE.search(title)

                created_at = hit.get("created_at") or ""
                date_found = None
                if created_at:
                    try:
                        date_found = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    except Exception:
                        pass

                results.append(
                    Startup(
                        company_name=m.group(1).strip(),
                        description=title,
                        funding_stage=stage.group(0) if stage else "",
                        amount_raised=amount.group(0) if amount else "",
                        source="Hacker News",
                        source_url=hit.get("url")
                        or f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                        date_found=date_found,
                    )
                )

        return results
