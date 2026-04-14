"""Scheduled entry point — wraps main.run() with file logging and timeout.

Used by scheduling/ templates (cron, Task Scheduler, launchd, GitHub Actions).
"""

import logging
import os
import sys
import threading
from datetime import datetime
from pathlib import Path

MAX_RUNTIME_SECONDS = 15 * 60
LOG_DIR = Path(__file__).parent / "logs"


def _setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(exist_ok=True)
    log_file = LOG_DIR / f"{datetime.now().strftime('%Y-%m-%d')}.log"
    logger = logging.getLogger("startup_radar")
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s  %(levelname)s  %(message)s", datefmt="%H:%M:%S")
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.addHandler(ch)
    return logger


def main() -> int:
    os.chdir(Path(__file__).parent)
    logger = _setup_logging()
    logger.info("Startup Radar daily run starting")

    def _timeout():
        logger.error(f"Run timed out after {MAX_RUNTIME_SECONDS // 60} minutes")
        os._exit(1)

    timer = threading.Timer(MAX_RUNTIME_SECONDS, _timeout)
    timer.daemon = True
    timer.start()

    try:
        from main import run
        rc = run()
        timer.cancel()
        logger.info("Daily run completed successfully")
        return rc
    except Exception as e:
        timer.cancel()
        logger.error(f"Daily run failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
