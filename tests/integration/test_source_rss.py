"""RSS source integration tests.

Phase 13: the RSS source fetches the feed body via the shared ``httpx.Client``
and hands bytes to ``feedparser.parse``. Tests stub both layers — ``get_client``
returns a fake client yielding canned bytes, and ``feedparser.parse`` is
monkeypatched to return a synthetic ``FeedParserDict``. The contract under
test is unchanged: ``RSSSource.fetch(cfg) -> list[Startup]`` across populated,
empty, and failure cases.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import feedparser
import httpx
import pytest
import yaml

from startup_radar.config import AppConfig
from startup_radar.config.schema import RSSFeed
from startup_radar.sources import rss as rss_module
from startup_radar.sources.rss import RSSSource

EXAMPLE = Path(__file__).resolve().parents[2] / "config.example.yaml"


def _cfg() -> AppConfig:
    with open(EXAMPLE, encoding="utf-8") as f:
        return AppConfig.model_validate(yaml.safe_load(f))


@pytest.fixture
def rss_cfg() -> AppConfig:
    cfg = _cfg()
    cfg.sources.rss.enabled = True
    cfg.sources.rss.feeds = [RSSFeed(name="Example", url="https://example.test/funding.rss")]
    return cfg


def _feed(entries: list[dict[str, Any]]) -> feedparser.util.FeedParserDict:
    """Build a FeedParserDict mimicking feedparser.parse() output."""
    parsed = feedparser.util.FeedParserDict()
    parsed.entries = [feedparser.util.FeedParserDict(e) for e in entries]
    parsed.bozo = 0
    return parsed


class _FakeResp:
    content = b"<rss/>"

    def raise_for_status(self) -> None:
        return None


class _FakeClient:
    def get(self, _url: str) -> _FakeResp:
        return _FakeResp()


def _stub_client(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rss_module, "get_client", lambda _cfg: _FakeClient())


def test_rss_happy_path(rss_cfg: AppConfig, monkeypatch: pytest.MonkeyPatch) -> None:
    """Feed with >=2 funding-shaped items → Startup rows with amount + company."""
    canned = _feed(
        [
            {
                "title": "Acme raises $5M Series A to reinvent widgets",
                "summary": "Acme, a widget startup, raised $5M Series A led by Sequoia.",
                "link": "https://example.test/acme",
            },
            {
                "title": "Globex secures $12M Series B",
                "summary": "Globex secured $12M Series B funding.",
                "link": "https://example.test/globex",
            },
            {
                "title": "Unrelated post about cats",
                "summary": "Not a funding item.",
                "link": "https://example.test/cats",
            },
        ]
    )
    _stub_client(monkeypatch)
    monkeypatch.setattr(
        rss_module, "feedparser", type("M", (), {"parse": staticmethod(lambda _b: canned)})
    )
    out = RSSSource().fetch(rss_cfg)
    assert len(out) == 2
    first = out[0]
    assert first.company_name == "Acme"
    assert first.source == "Example"
    assert first.amount_raised.startswith("$")
    assert first.funding_stage.lower().startswith("series")


def test_rss_empty_feed(rss_cfg: AppConfig, monkeypatch: pytest.MonkeyPatch) -> None:
    """Valid feed with zero entries → [] cleanly."""
    canned = _feed([])
    _stub_client(monkeypatch)
    monkeypatch.setattr(
        rss_module, "feedparser", type("M", (), {"parse": staticmethod(lambda _b: canned)})
    )
    assert RSSSource().fetch(rss_cfg) == []


def test_rss_fetch_exception_logs_and_returns_empty(
    rss_cfg: AppConfig,
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """feedparser raises (e.g. malformed XML) → warn + []."""

    def _boom(_b: bytes) -> Any:
        raise RuntimeError("malformed feed")

    _stub_client(monkeypatch)
    monkeypatch.setattr(rss_module, "feedparser", type("M", (), {"parse": staticmethod(_boom)}))
    caplog.set_level(logging.WARNING, logger="startup_radar.sources.rss")
    out = RSSSource().fetch(rss_cfg)
    assert out == []
    assert any(r.name.endswith("rss") and "fetch_failed" in r.message for r in caplog.records)


def test_rss_retries_then_succeeds(rss_cfg: AppConfig, monkeypatch: pytest.MonkeyPatch) -> None:
    """Two httpx.ConnectErrors then a 200 → retry helper unwraps via shared client."""
    calls = {"n": 0}
    canned = _feed(
        [
            {
                "title": "Acme raises $5M Series A",
                "summary": "Acme raised $5M Series A.",
                "link": "https://example.test/acme",
            }
        ]
    )

    class _FlakyClient:
        def get(self, _url: str) -> _FakeResp:
            calls["n"] += 1
            if calls["n"] < 3:
                raise httpx.ConnectError("transient")
            return _FakeResp()

    monkeypatch.setattr(rss_module, "get_client", lambda _cfg: _FlakyClient())
    monkeypatch.setattr(
        rss_module, "feedparser", type("M", (), {"parse": staticmethod(lambda _b: canned)})
    )
    out = RSSSource().fetch(rss_cfg)
    assert calls["n"] == 3
    assert len(out) == 1
    assert out[0].company_name == "Acme"
