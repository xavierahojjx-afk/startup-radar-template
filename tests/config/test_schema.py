"""Pydantic schema unit tests."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from startup_radar.config import AppConfig, ConfigError, load_config

EXAMPLE = Path(__file__).resolve().parents[2] / "config.example.yaml"


def _example() -> dict:
    with open(EXAMPLE, encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_example_config_parses() -> None:
    cfg = AppConfig.model_validate(_example())
    assert cfg.targets.min_stage == "series-a"
    assert cfg.sources.rss.enabled is True
    assert cfg.output.sqlite.path == "startup_radar.db"


def test_missing_required_section_fails() -> None:
    raw = _example()
    del raw["targets"]
    with pytest.raises(ValidationError):
        AppConfig.model_validate(raw)


def test_unknown_top_level_key_fails() -> None:
    raw = _example()
    raw["sourcs"] = {}
    with pytest.raises(ValidationError):
        AppConfig.model_validate(raw)


def test_invalid_stage_fails() -> None:
    raw = _example()
    raw["targets"]["min_stage"] = "series-zzz"
    with pytest.raises(ValidationError):
        AppConfig.model_validate(raw)


def test_sic_codes_accepts_empty_list() -> None:
    raw = _example()
    raw["sources"]["sec_edgar"]["industry_sic_codes"] = []
    cfg = AppConfig.model_validate(raw)
    assert cfg.sources.sec_edgar.industry_sic_codes == []


def test_loader_wraps_validation_error(tmp_path: Path) -> None:
    bad = tmp_path / "config.yaml"
    bad.write_text("user:\n  name: x\n")
    with pytest.raises(ConfigError) as exc:
        load_config(bad)
    assert "targets" in str(exc.value) or "sources" in str(exc.value)


def test_loader_yaml_error(tmp_path: Path) -> None:
    bad = tmp_path / "config.yaml"
    bad.write_text("::: not yaml :::")
    with pytest.raises(ConfigError):
        load_config(bad)
