"""Phase 3: company-name normalization unit tests."""

from startup_radar.parsing.normalize import dedup_key, normalize_company


def test_canonical_openai_case() -> None:
    """The canonical 'OpenAI vs Open AI Inc.' case from docs/CRITIQUE_APPENDIX.md."""
    assert normalize_company("OpenAI") == normalize_company("Open AI Inc.")


def test_strips_legal_suffixes() -> None:
    assert normalize_company("Acme Corp") == normalize_company("acme")
    assert normalize_company("Foo Labs LLC") == normalize_company("Foo")
    assert normalize_company("WeWork") == normalize_company("We Work")


def test_dedup_key_alias() -> None:
    assert dedup_key("Open AI Inc.") == normalize_company("Open AI Inc.")
