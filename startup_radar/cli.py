"""Startup Radar — Typer CLI. Single entry point for run / serve / deepdive."""

from __future__ import annotations

import io
import logging
import os
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer

app = typer.Typer(
    name="startup-radar",
    help="Personal startup discovery radar — RSS/HN/EDGAR/Gmail → SQLite → Streamlit.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

_MAX_SCHEDULED_RUNTIME_SEC = 15 * 60
_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"


# --- shared helpers --------------------------------------------------------


def _setup_scheduled_logging() -> logging.Logger:
    _LOG_DIR.mkdir(exist_ok=True)
    log_file = _LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.log"
    logger = logging.getLogger("startup_radar")
    logger.setLevel(logging.INFO)
    if logger.handlers:
        return logger
    fmt = logging.Formatter("%(asctime)s  %(levelname)s  %(message)s", datefmt="%H:%M:%S")
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    return logger


class _LogStream(io.TextIOBase):
    """Redirects print() output into the logger so the pipeline's step-by-step
    messages land in logs/YYYY-MM-DD.log. Temporary — Phase 13 replaces with structlog."""

    encoding = "utf-8"

    def __init__(self, log: logging.Logger):
        self._log = log

    def write(self, msg: str) -> int:
        for line in msg.rstrip().splitlines():
            stripped = line.strip()
            if stripped:
                self._log.info(stripped)
        return len(msg)

    def flush(self) -> None:
        pass


def _pipeline() -> int:
    """The actual pipeline. Mirrors pre-Phase-4 main.py:run()."""
    import database
    from startup_radar.config import load_config
    from startup_radar.filters import StartupFilter
    from startup_radar.models import Startup
    from startup_radar.parsing.normalize import dedup_key
    from startup_radar.sources.registry import SOURCES

    print("=" * 60)
    print("Startup Radar")
    print(f"Run time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    cfg = load_config()
    sqlite_cfg = cfg.output.sqlite
    if sqlite_cfg.enabled and sqlite_cfg.path:
        database.set_db_path(sqlite_cfg.path)
    database.init_db()

    all_startups: list[Startup] = []
    for key, source in SOURCES.items():
        sub_cfg = getattr(cfg.sources, key, None)
        if sub_cfg is None or not getattr(sub_cfg, "enabled", False):
            continue
        print(f"\n[{source.name}] Fetching...")
        found = source.fetch(cfg)
        print(f"  {len(found)} candidate(s)")
        all_startups.extend(found)

    print(f"\nTotal extracted: {len(all_startups)}")
    filtered = StartupFilter(cfg).filter(all_startups)
    print(f"After filter: {len(filtered)}")

    seen: set[str] = set()
    deduped: list[Startup] = []
    for s in filtered:
        key = dedup_key(s.company_name)
        if key and key not in seen:
            seen.add(key)
            deduped.append(s)
    if len(deduped) < len(filtered):
        print(f"After dedup: {len(deduped)}")

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

    sheets_cfg = cfg.output.google_sheets
    if sheets_cfg.enabled and fresh:
        try:
            from sinks import google_sheets

            google_sheets.append_startups(sheets_cfg.sheet_id, fresh)
            print(f"Wrote {len(fresh)} to Google Sheet")
        except Exception as e:
            print(f"Google Sheets write failed: {e}")

    print("\nDone.")
    return 0


# --- commands --------------------------------------------------------------


@app.command()
def run(
    scheduled: Annotated[
        bool,
        typer.Option(
            "--scheduled",
            help="Log to logs/YYYY-MM-DD.log with a 15-min timeout (cron mode).",
        ),
    ] = False,
) -> None:
    """Run the discovery pipeline once."""
    if not scheduled:
        raise typer.Exit(code=_pipeline())

    logger = _setup_scheduled_logging()
    logger.info("Startup Radar scheduled run starting")

    def _timeout() -> None:
        logger.error(f"Run timed out after {_MAX_SCHEDULED_RUNTIME_SEC // 60} minutes")
        os._exit(1)

    timer = threading.Timer(_MAX_SCHEDULED_RUNTIME_SEC, _timeout)
    timer.daemon = True
    timer.start()

    old_stdout = sys.stdout
    sys.stdout = _LogStream(logger)
    try:
        rc = _pipeline()
        sys.stdout = old_stdout
        timer.cancel()
        logger.info("Scheduled run completed successfully")
        raise typer.Exit(code=rc)
    except typer.Exit:
        raise
    except Exception as e:
        sys.stdout = old_stdout
        timer.cancel()
        msg = str(e).lower()
        if "token" in msg or "credentials" in msg or "refresh" in msg:
            logger.error(f"OAuth token expired or invalid: {e}")
            logger.error("Delete token.json and run `startup-radar run` to re-authenticate.")
        else:
            logger.error(f"Scheduled run failed: {e}", exc_info=True)
        raise typer.Exit(code=1) from e


@app.command()
def serve(
    port: Annotated[int, typer.Option(help="Port the dashboard binds to.")] = 8501,
) -> None:
    """Open the Streamlit dashboard."""
    import subprocess

    repo_root = Path(__file__).resolve().parent.parent
    app_path = repo_root / "app.py"
    cmd = [sys.executable, "-m", "streamlit", "run", str(app_path), "--server.port", str(port)]
    raise typer.Exit(code=subprocess.call(cmd))


@app.command()
def deepdive(
    company: Annotated[str, typer.Argument(help="Company name, e.g. 'Anthropic'.")],
) -> None:
    """Generate a one-page research brief (.docx) for COMPANY."""
    from startup_radar.research.deepdive import generate

    path = generate(company)
    typer.echo(f"Report saved: {path}")


if __name__ == "__main__":
    app()
