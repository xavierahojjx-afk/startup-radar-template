"""RSS source — pulls funding announcements from public feeds.

No authentication required. Works out of the box.
"""

from __future__ import annotations

import logging
import re
import socket
from datetime import datetime
from typing import Any

import feedparser
from bs4 import BeautifulSoup

from startup_radar.models import Startup
from startup_radar.parsing.funding import AMOUNT_RE, COMPANY_SUBJECT_RE, STAGE_RE
from startup_radar.sources.base import Source

# feedparser has no per-call timeout; cap the underlying socket so a hung
# feed can't block the daily run forever.
socket.setdefaulttimeout(20)

log = logging.getLogger(__name__)


def _strip_html(html: str) -> str:
    if not html:
        return ""
    return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)


def _extract_company(title: str) -> str:
    m = COMPANY_SUBJECT_RE.match(title)
    if m:
        return m.group(1).strip()
    parts = re.split(
        r"\s+(?:raises|secures|closes|lands|nabs|announces|picks up)\s+",
        title,
        maxsplit=1,
        flags=re.IGNORECASE,
    )
    if len(parts) == 2:
        return parts[0].strip()
    return ""


def _is_funding_item(title: str, summary: str) -> bool:
    text = f"{title} {summary}".lower()
    signals = [
        "raises",
        "raised",
        "funding",
        "series ",
        "seed round",
        "closes $",
        "secures $",
        "nabs $",
        "lands $",
    ]
    return any(s in text for s in signals)


class RSSSource(Source):
    name = "RSS"
    enabled_key = "rss"

    def fetch(self, cfg: dict[str, Any]) -> list[Startup]:
        rss_cfg = cfg.get("sources", {}).get(self.enabled_key, {})
        if not rss_cfg.get("enabled"):
            return []
        out: list[Startup] = []
        for feed in rss_cfg.get("feeds", []):
            try:
                out.extend(self._fetch_one(feed["url"], feed.get("name", feed["url"])))
            except Exception as e:
                log.warning(
                    "source.fetch_failed",
                    extra={"source": self.name, "feed": feed.get("name"), "err": str(e)},
                )
        return out

    def _fetch_one(self, feed_url: str, source_name: str) -> list[Startup]:
        parsed = feedparser.parse(feed_url)
        results: list[Startup] = []
        for entry in parsed.entries:
            title = entry.get("title", "") or ""
            summary = _strip_html(entry.get("summary", "") or entry.get("description", ""))
            if not _is_funding_item(title, summary):
                continue
            company = _extract_company(title)
            if not company:
                continue

            amount_match = AMOUNT_RE.search(f"{title} {summary}")
            stage_match = STAGE_RE.search(f"{title} {summary}")

            date_found = None
            if entry.get("published_parsed"):
                try:
                    date_found = datetime(*entry.published_parsed[:6])
                except Exception:
                    date_found = None

            results.append(
                Startup(
                    company_name=company,
                    description=summary[:300],
                    funding_stage=stage_match.group(0) if stage_match else "",
                    amount_raised=amount_match.group(0) if amount_match else "",
                    location="",
                    source=source_name,
                    source_url=entry.get("link", ""),
                    date_found=date_found,
                )
            )
        return results
