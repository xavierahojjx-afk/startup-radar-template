"""Load and validate config.yaml."""

from pathlib import Path
import yaml

BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.yaml"
EXAMPLE_FILE = BASE_DIR / "config.example.yaml"


class ConfigError(Exception):
    pass


def load_config() -> dict:
    """Load config.yaml, falling back to config.example.yaml for first runs."""
    path = CONFIG_FILE if CONFIG_FILE.exists() else EXAMPLE_FILE
    if not path.exists():
        raise ConfigError(
            "No config.yaml or config.example.yaml found. "
            "Run `claude` and invoke the /setup skill, or copy config.example.yaml to config.yaml."
        )
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    _validate(cfg)
    return cfg


def _validate(cfg: dict) -> None:
    for key in ("user", "targets", "sources", "output"):
        if key not in cfg:
            raise ConfigError(f"config.yaml missing required section: {key}")
