"""Config package — pydantic schema + loader. Single source of truth for config.yaml shape."""

from startup_radar.config.loader import ConfigError, load_config
from startup_radar.config.schema import (
    AppConfig,
    ConnectionsConfig,
    DeepDiveConfig,
    OutputConfig,
    SourcesConfig,
    TargetsConfig,
    UserConfig,
)

__all__ = [
    "AppConfig",
    "ConfigError",
    "ConnectionsConfig",
    "DeepDiveConfig",
    "OutputConfig",
    "SourcesConfig",
    "TargetsConfig",
    "UserConfig",
    "load_config",
]
