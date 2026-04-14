"""SEC EDGAR Form D source.

Form D is filed by nearly every US private company raising a priced round
under Regulation D. It's authoritative, free, and catches raises that never
get press coverage. Data trails by a few days to weeks.

EDGAR is unauthenticated but requires a User-Agent with contact info.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

import requests

from models import Startup

EDGAR_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
EDGAR_HEADERS = {
    "User-Agent": "startup-radar-template (github.com/xavierahojjx-afk/startup-radar-template)",
    "Accept": "application/json",
}


def fetch(
    lookback_days: int = 7,
    min_amount_musd: float = 5.0,
    sic_codes: Iterable[str] | None = None,
) -> list[Startup]:
    """Search EDGAR full-text search for recent Form D filings."""
    end = datetime.utcnow().date()
    start = end - timedelta(days=lookback_days)

    params = {
        "q": "\"Form D\"",
        "dateRange": "custom",
        "startdt": start.isoformat(),
        "enddt": end.isoformat(),
        "forms": "D",
    }
    if sic_codes:
        params["sic"] = ",".join(sic_codes)

    try:
        resp = requests.get(EDGAR_SEARCH_URL, params=params, headers=EDGAR_HEADERS, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  EDGAR error: {e}")
        return []

    hits = data.get("hits", {}).get("hits", [])
    results: list[Startup] = []

    for hit in hits:
        src = hit.get("_source", {})
        display_names = src.get("display_names") or []
        if not display_names:
            continue
        company = display_names[0]
        if "(" in company:
            company = company.split("(")[0].strip()

        file_date = src.get("file_date") or ""
        date_found = None
        if file_date:
            try:
                date_found = datetime.fromisoformat(file_date)
            except Exception:
                pass

        adsh = src.get("adsh", "")
        cik = (src.get("ciks") or [""])[0]
        url = (
            f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=D"
            if cik else ""
        )

        results.append(Startup(
            company_name=company,
            description="Form D filing (SEC EDGAR)",
            funding_stage="",
            amount_raised="",
            location="",
            source="SEC EDGAR",
            source_url=url,
            date_found=date_found,
        ))

    return results
