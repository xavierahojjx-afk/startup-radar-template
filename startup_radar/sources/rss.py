"""RSS source — pulls funding announcements from public feeds.

No authentication required. Works out of the box.
"""

from __future__ import annotations

import re
from datetime import datetime

import feedparser
import httpx
from bs4 import BeautifulSoup

from startup_radar.config import AppConfig
from startup_radar.http import get_client
from startup_radar.models import Startup
from startup_radar.observability.logging import get_logger
from startup_radar.parsing.funding import AMOUNT_RE, COMPANY_SUBJECT_RE, STAGE_RE
from startup_radar.sources._retry import retry
from startup_radar.sources.base import Source

log = get_logger(__name__)


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

    def healthcheck(self, cfg: AppConfig, *, network: bool = False) -> tuple[bool, str]:
        feeds = cfg.sources.rss.feeds
        if not feeds:
            return (False, "no feeds configured")
        if not network:
            return (True, f"{len(feeds)} feed(s) configured")

        url = str(feeds[0].url)
        client = get_client(cfg)
        try:
            r = client.head(url)
            # Some feed hosts return 405 for HEAD; fall back to GET.
            if r.status_code == 405:
                r = client.get(url)
            if r.status_code < 400:
                return (True, f"{len(feeds)} feed(s); first feed HTTP {r.status_code}")
            return (False, f"first feed HTTP {r.status_code}")
        except httpx.HTTPError as e:
            return (False, f"first feed unreachable: {e.__class__.__name__}")

    def fetch(self, cfg: AppConfig, storage=None) -> list[Startup]:
        rss_cfg = cfg.sources.rss
        if not rss_cfg.enabled:
            return []
        client = get_client(cfg)
        out: list[Startup] = []
        for feed in rss_cfg.feeds:
            try:
                out.extend(self._fetch_one(client, str(feed.url), feed.name))
            except Exception as e:
                log.warning(
                    "source.fetch_failed",
                    source=self.name,
                    feed=feed.name,
                    err=str(e),
                )
        return out

    def _fetch_one(self, client: httpx.Client, feed_url: str, source_name: str) -> list[Startup]:
        def _get_and_parse() -> feedparser.util.FeedParserDict:
            r = client.get(feed_url)
            r.raise_for_status()
            return feedparser.parse(r.content)

        parsed = retry(
            _get_and_parse,
            on=(httpx.HTTPError, TimeoutError),
            context={"source": self.name, "feed": source_name},
        )
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
