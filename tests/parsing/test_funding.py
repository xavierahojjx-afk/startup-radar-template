"""Phase 3: parse_amount_musd unit tests."""

from startup_radar.parsing.funding import STAGE_RE, parse_amount_musd


def test_parse_millions() -> None:
    assert parse_amount_musd("$2.5M") == 2.5
    assert parse_amount_musd("raised $25 million") == 25.0
    assert parse_amount_musd("$1,200M") == 1200.0


def test_parse_billions() -> None:
    assert parse_amount_musd("$1B") == 1000.0
    assert parse_amount_musd("$2.5 billion") == 2500.0


def test_parse_unparseable_returns_none() -> None:
    assert parse_amount_musd("") is None
    assert parse_amount_musd(None) is None
    assert parse_amount_musd("an undisclosed sum") is None


def test_stage_re_seed_round_unification() -> None:
    """Phase 3 risk #4: rss superset includes 'Seed Round'; HN/Gmail variant only matched bare 'Seed'.

    Both forms must now match — single STAGE_RE replaces three duplicates.
    """
    assert STAGE_RE.search("Acme raises Seed Round") is not None
    assert STAGE_RE.search("Acme raises Seed") is not None
    assert STAGE_RE.search("Series A") is not None
