"""LinkedIn connections — import CSV export and search for warm intros.

Two tiers of intro signal:
  Tier 1 — direct connections at the target company
  Tier 2 — connections at the target company's investors (requires a
           DeepDive report to have extracted investor names first)
"""

import csv
from pathlib import Path

import pandas as pd

import database


def import_from_csv(csv_path: str) -> int:
    """Import a LinkedIn Connections.csv export. Returns count imported."""
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"Connections CSV not found: {csv_path}")

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    header_idx = 0
    for i, line in enumerate(lines):
        if line.startswith("First Name,") or "First Name" in line and "Last Name" in line:
            header_idx = i
            break

    reader = csv.DictReader(lines[header_idx:])
    rows = [row for row in reader if row.get("First Name") or row.get("Last Name")]
    return database.import_connections(rows)


def tier1_intros(company_name: str) -> pd.DataFrame:
    """Direct connections working at the target company."""
    return database.search_connections_by_company(company_name)


def tier2_intros(investor_names: list[str]) -> pd.DataFrame:
    """Connections at the target company's investor firms."""
    if not investor_names:
        return pd.DataFrame()
    return database.search_connections_by_companies(investor_names)
