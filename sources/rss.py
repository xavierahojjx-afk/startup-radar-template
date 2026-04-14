"""RSS source — pulls funding announcements from public feeds.

No authentication required. Works out of the box.
"""

import re
from datetime import datetime
from typing import Iterable

import feedparser
from bs4 import BeautifulSoup

from models import Startup


_AMOUNT_RE = re.compile(
    r"\$\s*[\d,.]+\s*(?:B|M|billion|million)\b",
    re.IGNORECASE,
)
_STAGE_RE = re.compile(
    r"\b(Pre-?Seed|Seed(?:\s+Round)?|Series\s+[A-F]\d?\+?)\b",
    re.IGNORECASE,
)
_COMPANY_SUBJECT_RE = re.compile(
    r"^([A-Z][\w\-.&' ]{1,40}?)(?:\s+raises|\s+secures|\s+closes|\s+lands|\s+nabs|\s+announces|\s+picks up)",
    re.IGNORECASE,
)


def _strip_html(html: str) -> str:
    if not html:
        return ""
    return BeautifulSoup(html, "html.parser").get_text(" ", strip=True)


def _extract_company(title: str) -> str:
    m = _COMPANY_SUBJECT_RE.match(title)
    if m:
        return m.group(1).strip()
    parts = re.split(r"\s+(?:raises|secures|closes|lands|nabs|announces|picks up)\s+",
                     title, maxsplit=1, flags=re.IGNORECASE)
    if len(parts) == 2:
        return parts[0].strip()
    return ""


def _is_funding_item(title: str, summary: str) -> bool:
    text = f"{title} {summary}".lower()
    signals = ["raises", "raised", "funding", "series ", "seed round",
               "closes $", "secures $", "nabs $", "lands $"]
    return any(s in text for s in signals)


def fetch(feed_url: str, source_name: str) -> list[Startup]:
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

        amount_match = _AMOUNT_RE.search(f"{title} {summary}")
        stage_match = _STAGE_RE.search(f"{title} {summary}")

        date_found = None
        if entry.get("published_parsed"):
            try:
                date_found = datetime(*entry.published_parsed[:6])
            except Exception:
                date_found = None

        results.append(Startup(
            company_name=company,
            description=summary[:300],
            funding_stage=stage_match.group(0) if stage_match else "",
            amount_raised=amount_match.group(0) if amount_match else "",
            location="",
            source=source_name,
            source_url=entry.get("link", ""),
            date_found=date_found,
        ))
    return results


def fetch_all(feeds: Iterable[dict]) -> list[Startup]:
    out: list[Startup] = []
    for feed in feeds:
        try:
            out.extend(fetch(feed["url"], feed.get("name", feed["url"])))
        except Exception as e:
            print(f"  RSS error ({feed.get('name')}): {e}")
    return out
