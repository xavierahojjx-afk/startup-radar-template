"""Startup Radar — pipeline entry point.

Runs enabled sources from config.yaml, filters results by user criteria,
and writes matches to SQLite (and optionally Google Sheets).
"""

import re
import sys
from datetime import datetime

from config_loader import load_config
from filters import StartupFilter
from models import Startup
import database


def _dedup(startups: list[Startup]) -> list[Startup]:
    seen: set[str] = set()
    out: list[Startup] = []
    for s in startups:
        key = re.sub(r"[\s.\-]+", "", s.company_name.lower())
        if key and key not in seen:
            seen.add(key)
            out.append(s)
    return out


def run() -> int:
    print("=" * 60)
    print("Startup Radar")
    print(f"Run time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    cfg = load_config()

    output_cfg = cfg.get("output", {})
    sqlite_cfg = output_cfg.get("sqlite", {})
    if sqlite_cfg.get("enabled", True) and sqlite_cfg.get("path"):
        database.set_db_path(sqlite_cfg["path"])

    database.init_db()

    all_startups: list[Startup] = []
    sources_cfg = cfg.get("sources", {})

    # --- RSS ---
    rss_cfg = sources_cfg.get("rss", {})
    if rss_cfg.get("enabled"):
        print("\n[RSS] Fetching...")
        from sources import rss
        found = rss.fetch_all(rss_cfg.get("feeds", []))
        print(f"  {len(found)} candidate(s)")
        all_startups.extend(found)

    # --- Hacker News ---
    hn_cfg = sources_cfg.get("hackernews", {})
    if hn_cfg.get("enabled"):
        print("\n[HN] Fetching...")
        from sources import hackernews
        found = hackernews.fetch(
            hn_cfg.get("queries", []),
            lookback_hours=int(hn_cfg.get("lookback_hours", 48)),
        )
        print(f"  {len(found)} candidate(s)")
        all_startups.extend(found)

    # --- SEC EDGAR ---
    edgar_cfg = sources_cfg.get("sec_edgar", {})
    if edgar_cfg.get("enabled"):
        print("\n[EDGAR] Fetching Form D filings...")
        from sources import sec_edgar
        found = sec_edgar.fetch(
            lookback_days=int(edgar_cfg.get("lookback_days", 7)),
            min_amount_musd=float(edgar_cfg.get("min_amount_musd", 5)),
            sic_codes=edgar_cfg.get("industry_sic_codes") or None,
        )
        print(f"  {len(found)} candidate(s)")
        all_startups.extend(found)

    # --- Optional: Gmail ---
    gmail_cfg = sources_cfg.get("gmail", {})
    if gmail_cfg.get("enabled"):
        print("\n[Gmail] Fetching...")
        try:
            from sources import gmail as gmail_src
            found = gmail_src.fetch(gmail_cfg)
            print(f"  {len(found)} candidate(s)")
            all_startups.extend(found)
        except Exception as e:
            print(f"  Gmail source failed: {e}")

    print(f"\nTotal extracted: {len(all_startups)}")

    # --- Filter ---
    flt = StartupFilter(cfg)
    filtered = flt.filter(all_startups)
    print(f"After filter: {len(filtered)}")

    # --- Dedup ---
    deduped = _dedup(filtered)
    if len(deduped) < len(filtered):
        print(f"After dedup: {len(deduped)}")

    # --- Write ---
    existing = database.get_existing_companies()
    rejected = database.get_rejected_companies()
    fresh = [
        s for s in deduped
        if s.company_name.lower().strip() not in existing
        and s.company_name.lower().strip() not in rejected
    ]
    skipped = len(deduped) - len(fresh)
    if skipped:
        print(f"Skipped {skipped} already-seen or rejected")

    if fresh:
        added = database.insert_startups(fresh)
        print(f"Added {added} new startup(s) to SQLite")
        for s in fresh:
            amount = f" | {s.amount_raised}" if s.amount_raised else ""
            stage = f" | {s.funding_stage}" if s.funding_stage else ""
            print(f"  {s.company_name}{stage}{amount}  [{s.source}]")
    else:
        print("No new startups to add")

    # --- Optional: Google Sheets sink ---
    sheets_cfg = output_cfg.get("google_sheets", {})
    if sheets_cfg.get("enabled") and fresh:
        try:
            from sinks import google_sheets
            google_sheets.append_startups(sheets_cfg["sheet_id"], fresh)
            print(f"Wrote {len(fresh)} to Google Sheet")
        except Exception as e:
            print(f"Google Sheets write failed: {e}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(run())
