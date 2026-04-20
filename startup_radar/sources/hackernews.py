"""Hacker News source — Algolia search API.

Free, no auth. Use it to fish for "raised Series X" threads.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import httpx

from startup_radar.config import AppConfig
from startup_radar.http import get_client
from startup_radar.models import Startup
from startup_radar.observability.logging import get_logger
from startup_radar.parsing.funding import AMOUNT_RE, COMPANY_SUBJECT_RE, STAGE_RE
from startup_radar.sources._retry import retry
from startup_radar.sources.base import Source

ALGOLIA_URL = "https://hn.algolia.com/api/v1/search_by_date"

log = get_logger(__name__)


class HackerNewsSource(Source):
    name = "Hacker News"
    enabled_key = "hackernews"

    def healthcheck(self, cfg: AppConfig, *, network: bool = False) -> tuple[bool, str]:
        queries = cfg.sources.hackernews.queries
        if not queries:
            return (False, "no queries configured")
        if not network:
            return (True, f"{len(queries)} query(ies) configured")

        try:
            r = get_client(cfg).get(
                "https://hn.algolia.com/api/v1/search",
                params={"query": "startup", "hitsPerPage": "1"},
            )
            if r.status_code == 200:
                return (True, "Algolia API HTTP 200")
            return (False, f"Algolia API HTTP {r.status_code}")
        except httpx.HTTPError as e:
            return (False, f"Algolia unreachable: {e.__class__.__name__}")

    def fetch(self, cfg: AppConfig, storage=None) -> list[Startup]:
        hn_cfg = cfg.sources.hackernews
        if not hn_cfg.enabled:
            return []

        queries = hn_cfg.queries
        lookback_hours = int(hn_cfg.lookback_hours)
        cutoff = datetime.utcnow() - timedelta(hours=lookback_hours)
        cutoff_ts = int(cutoff.timestamp())
        client = get_client(cfg)

        seen_titles: set[str] = set()
        results: list[Startup] = []

        for query in queries:
            try:
                resp = retry(
                    lambda q=query: client.get(
                        ALGOLIA_URL,
                        params={
                            "query": q,
                            "tags": "story",
                            "numericFilters": f"created_at_i>{cutoff_ts}",
                            "hitsPerPage": 50,
                        },
                    ),
                    on=(httpx.HTTPError, TimeoutError),
                    context={"source": self.name, "query": query},
                )
                resp.raise_for_status()
                hits = resp.json().get("hits", [])
            except Exception as e:
                log.warning(
                    "source.fetch_failed",
                    source=self.name,
                    query=query,
                    err=str(e),
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
