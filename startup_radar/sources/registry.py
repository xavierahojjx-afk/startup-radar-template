"""Source registry. Adding a source = one line here + one file in this directory."""

from __future__ import annotations

from startup_radar.sources.base import Source
from startup_radar.sources.gmail import GmailSource
from startup_radar.sources.hackernews import HackerNewsSource
from startup_radar.sources.rss import RSSSource
from startup_radar.sources.sec_edgar import SECEdgarSource

SOURCES: dict[str, Source] = {
    s.enabled_key: s for s in (RSSSource(), HackerNewsSource(), SECEdgarSource(), GmailSource())
}
