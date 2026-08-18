"""Data-quality tests: each defect is detected, treated, and reported."""

import pandas as pd
import pytest

from app.dq import (
    SIGN_BY_DIRECTION,
    IssueCode,
    Severity,
    _parse_slashed_date,
    clean_trades,
)
from app.loaders import load_trades_raw
from app.models import Direction


@pytest.fixture
def cleaned():
    return clean_trades(load_trades_raw())


def _issues_for(cleaned, code):
    return [issue for issue in cleaned.issues if issue.code == code]


def test_exact_duplicate_row_is_dropped_once(cleaned):
    """FIX-005 is delivered twice, identically."""
    assert (cleaned.trades["trade_id"] == "FIX-005").sum() == 1

    issues = _issues_for(cleaned, IssueCode.DUPLICATE_TRADE_ROW)
    assert [issue.entity_id for issue in issues] == ["FIX-005"]
    assert issues[0].severity == Severity.ERROR


def test_duplicate_removal_keeps_every_other_trade(cleaned):
    """Dedupe must drop exactly the duplicate rows and nothing else."""
    raw = load_trades_raw()
    duplicate_count = int(raw.duplicated().sum())

    assert duplicate_count == 1
    assert len(cleaned.trades) == len(raw) - duplicate_count
    assert cleaned.trades["trade_id"].is_unique
    assert set(cleaned.trades["trade_id"]) == set(raw["trade_id"])


def test_duplicate_would_otherwise_double_the_position():
    """The reason the duplicate matters, asserted rather than asserted-in-prose.

    The risk file carries one set of sensitivities for FIX-005, so leaving both
    rows in place doubles its face amount against unchanged risk.
    """
    raw = load_trades_raw()
    cleaned = clean_trades(raw).trades

    raw_face = raw.loc[raw["trade_id"] == "FIX-005", "quantity"].sum()
    clean_face = cleaned.loc[cleaned["trade_id"] == "FIX-005", "quantity"].sum()

    assert raw_face == 20000
    assert clean_face == 10000


def test_conflicting_rows_are_escalated_not_silently_deduped():
    """Same trade id, different economics: no automatic winner."""
    raw = load_trades_raw()
    conflicting = raw[raw["trade_id"] == "FIX-001"].copy()
    conflicting["trade_price"] = 97.5
    raw = pd.concat([raw, conflicting], ignore_index=True)

    result = clean_trades(raw)
    issues = _issues_for(result, IssueCode.CONFLICTING_TRADE_ROW)

    assert [issue.entity_id for issue in issues] == ["FIX-001"]
    assert issues[0].severity == Severity.ERROR
    assert result.trades["trade_id"].is_unique
    # First occurrence wins, so the original economics survive.
    assert result.trades.set_index("trade_id").at["FIX-001", "trade_price"] == 100.00


def test_malformed_date_is_repaired_to_iso(cleaned):
    """FIX-003 carries 07/28/2026 while the rest of the file is ISO."""
    trades = cleaned.trades.set_index("trade_id")
    assert trades.at["FIX-003", "trade_date"] == pd.Timestamp("2026-07-28")

    issues = _issues_for(cleaned, IssueCode.MALFORMED_TRADE_DATE)
    assert [issue.entity_id for issue in issues] == ["FIX-003"]
    assert "2026-07-28" in issues[0].treatment


def test_no_trade_dates_left_unparsed_after_cleaning(cleaned):
    assert cleaned.trades["trade_date"].notna().all()


def test_ambiguous_date_is_refused_rather_than_guessed():
    """07/08/2026 is valid as both readings; guessing would move it a month."""
    parsed, note = _parse_slashed_date("07/08/2026")

    assert parsed is None
    assert "ambiguous" in note


def test_unambiguous_dates_are_parsed_both_ways_round():
    assert _parse_slashed_date("07/28/2026")[0].isoformat() == "2026-07-28"
    assert _parse_slashed_date("28/07/2026")[0].isoformat() == "2026-07-28"


def test_ambiguous_date_in_the_blotter_is_escalated_and_left_null():
    raw = load_trades_raw()
    raw.loc[raw["trade_id"] == "FIX-003", "trade_date_raw"] = "07/08/2026"

    result = clean_trades(raw)
    issues = _issues_for(result, IssueCode.UNREPAIRABLE_TRADE_DATE)

    assert [issue.entity_id for issue in issues] == ["FIX-003"]
    assert issues[0].severity == Severity.ERROR
    assert pd.isna(result.trades.set_index("trade_id").at["FIX-003", "trade_date"])


def test_repaired_date_is_validated_against_settle_date():
    """A settle date before the trade date means the repair chose wrongly.

    This is the check that makes the MM/DD reading defensible rather than
    assumed, so it must actually fire when the dates are incoherent.
    """
    raw = load_trades_raw()
    raw.loc[raw["trade_id"] == "FIX-001", "settle_date"] = pd.Timestamp("2026-06-01")

    result = clean_trades(raw)
    issues = _issues_for(result, IssueCode.TRADE_DATE_AFTER_SETTLE_DATE)

    assert [issue.entity_id for issue in issues] == ["FIX-001"]


def test_real_blotter_dates_are_coherent(cleaned):
    """No coherence breach in the fixture: the repair stands up."""
    assert _issues_for(cleaned, IssueCode.TRADE_DATE_AFTER_SETTLE_DATE) == []


def test_negative_quantity_with_sell_becomes_a_magnitude(cleaned):
    """FIX-006 encodes the short twice: quantity -5 *and* direction SELL."""
    trades = cleaned.trades.set_index("trade_id")

    assert trades.at["FIX-006", "quantity"] == 5
    assert trades.at["FIX-006", "direction"] == "SELL"
    assert trades.at["FIX-006", "direction_sign"] == -1


def test_double_negative_would_have_flipped_the_position(cleaned):
    """Taken literally, -5 contracts sold reads as a long. It must not."""
    trades = cleaned.trades.set_index("trade_id")
    signed = trades.at["FIX-006", "quantity"] * trades.at["FIX-006", "direction_sign"]

    assert signed == -5


def test_quantity_sign_conflict_is_reported(cleaned):
    issues = _issues_for(cleaned, IssueCode.NEGATIVE_QUANTITY_WITH_DIRECTION)

    assert [issue.entity_id for issue in issues] == ["FIX-006"]
    assert issues[0].severity == Severity.ERROR


def test_all_quantities_are_non_negative_after_cleaning(cleaned):
    assert (cleaned.trades["quantity"] >= 0).all()


def test_direction_sign_covers_every_direction(cleaned):
    """PAY/RECEIVE must map as cleanly as BUY/SELL, or swaps lose their side."""
    assert cleaned.trades["direction_sign"].isin([-1, 1]).all()
    trades = cleaned.trades.set_index("trade_id")
    assert trades.at["FIX-002", "direction"] == "PAY"
    assert trades.at["FIX-002", "direction_sign"] == -1


def test_every_documented_direction_has_a_sign():
    """Guard the lookup against a new direction arriving without a sign.

    An unmapped direction would otherwise surface as a NaN cast error deep in
    the cleaning run, rather than here.
    """
    assert set(SIGN_BY_DIRECTION) == {member.value for member in Direction}


def test_missing_settle_date_is_reported_not_invented(cleaned):
    """FIX-007 has no settle date; inventing one would move it in or out."""
    issues = _issues_for(cleaned, IssueCode.MISSING_SETTLE_DATE)

    assert [issue.entity_id for issue in issues] == ["FIX-007"]
    assert issues[0].severity == Severity.WARNING
    assert pd.isna(cleaned.trades.set_index("trade_id").at["FIX-007", "settle_date"])


def test_helper_column_does_not_leak_downstream(cleaned):
    assert "trade_date_raw" not in cleaned.trades.columns


def test_issue_ordering_is_deterministic(cleaned):
    codes = [(issue.code.value, issue.entity_id) for issue in cleaned.issues]
    assert codes == sorted(codes)


def test_cleaning_does_not_mutate_the_caller_frame():
    """The raw frame stays available for reconciliation against the source."""
    raw = load_trades_raw()
    before = len(raw)

    clean_trades(raw)

    assert len(raw) == before
    assert raw["quantity"].min() < 0
