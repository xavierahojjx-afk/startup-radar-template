"""Startup Radar — pipeline entry point.

Runs enabled sources from config.yaml, filters results by user criteria,
and writes matches to SQLite (and optionally Google Sheets).
"""

import sys
from datetime import datetime

import database
from config_loader import load_config
from filters import StartupFilter
from startup_radar.models import Startup
from startup_radar.parsing.normalize import dedup_key
from startup_radar.sources.registry import SOURCES


def _dedup(startups: list[Startup]) -> list[Startup]:
    seen: set[str] = set()
    out: list[Startup] = []
    for s in startups:
        key = dedup_key(s.company_name)
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

    for key, source in SOURCES.items():
        if not sources_cfg.get(key, {}).get("enabled"):
            continue
        print(f"\n[{source.name}] Fetching...")
        found = source.fetch(cfg)
        print(f"  {len(found)} candidate(s)")
        all_startups.extend(found)

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
        s
        for s in deduped
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
