"""SEC EDGAR Form D source.

Form D is filed by nearly every US private company raising a priced round
under Regulation D. It's authoritative, free, and catches raises that never
get press coverage. Data trails by a few days to weeks.

EDGAR is unauthenticated but requires a User-Agent with contact info.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

import requests

from startup_radar.config import AppConfig
from startup_radar.models import Startup
from startup_radar.sources.base import Source

EDGAR_SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
EDGAR_HEADERS = {
    "User-Agent": "startup-radar-template (github.com/xavierahojjx-afk/startup-radar-template)",
    "Accept": "application/json",
}

log = logging.getLogger(__name__)


class SECEdgarSource(Source):
    name = "SEC EDGAR"
    enabled_key = "sec_edgar"

    def fetch(self, cfg: AppConfig) -> list[Startup]:
        edgar_cfg = cfg.sources.sec_edgar
        if not edgar_cfg.enabled:
            return []

        lookback_days = int(edgar_cfg.lookback_days)
        sic_codes = edgar_cfg.industry_sic_codes or None

        end = datetime.utcnow().date()
        start = end - timedelta(days=lookback_days)

        params: dict[str, Any] = {
            "q": '"Form D"',
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
            log.warning("source.fetch_failed", extra={"source": self.name, "err": str(e)})
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

            cik = (src.get("ciks") or [""])[0]
            url = (
                f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=D"
                if cik
                else ""
            )

            results.append(
                Startup(
                    company_name=company,
                    description="Form D filing (SEC EDGAR)",
                    funding_stage="",
                    amount_raised="",
                    location="",
                    source="SEC EDGAR",
                    source_url=url,
                    date_found=date_found,
                )
            )

        return results
