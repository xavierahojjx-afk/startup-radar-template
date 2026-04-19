"""Load and validate config.yaml → AppConfig."""

from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]
from pydantic import ValidationError

from startup_radar.config.schema import AppConfig

BASE_DIR = Path(__file__).resolve().parents[2]
CONFIG_FILE = BASE_DIR / "config.yaml"
EXAMPLE_FILE = BASE_DIR / "config.example.yaml"


class ConfigError(Exception):
    """Raised when config.yaml is missing, unparseable, or fails schema validation."""


def load_config(path: Path | None = None) -> AppConfig:
    """Load config.yaml, falling back to config.example.yaml for first runs.

    Returns a fully-typed AppConfig. Wraps pydantic ValidationError in a
    ConfigError whose message points at field paths.
    """
    if path is not None:
        src = path
    else:
        src = CONFIG_FILE if CONFIG_FILE.exists() else EXAMPLE_FILE

    if not src.exists():
        raise ConfigError(
            "No config.yaml or config.example.yaml found. "
            "Run `claude` and invoke the /setup skill, or copy config.example.yaml to config.yaml."
        )

    try:
        with open(src, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise ConfigError(f"{src} is not valid YAML: {e}") from e

    try:
        return AppConfig.model_validate(raw)
    except ValidationError as e:
        lines = [f"  {'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()]
        raise ConfigError(f"{src} failed validation:\n" + "\n".join(lines)) from e
