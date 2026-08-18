"""Positions engine tests, with the settlement rule as the centre of gravity."""

from datetime import date

import pandas as pd
import pytest

from app.dq import clean_trades
from app.issues import IssueCode, Severity
from app.loaders import load_trades_raw, to_records
from app.positions import Position, PositionStatus, build_positions

AS_OF = date(2026, 8, 5)


@pytest.fixture
def cleaned():
    return clean_trades(load_trades_raw()).trades


@pytest.fixture
def book(cleaned):
    return build_positions(cleaned, as_of=AS_OF)


def _position(book, instrument_id, product_type=None):
    rows = book.positions[book.positions["instrument_id"] == instrument_id]
    if product_type:
        rows = rows[rows["product_type"] == product_type]
    assert len(rows) == 1, f"expected exactly one position, got {len(rows)}"
    return rows.iloc[0]


def _issues_for(book, code):
    return [issue for issue in book.issues if issue.code == code]


# --- the settlement rule -----------------------------------------------------


def test_settled_bond_stays_open(book):
    """The rule that would empty the book if it were keyed on settle_date alone.

    FIX-001 settled on 2026-07-03, well before the as-of date. Settlement is
    when the bonds were *delivered*, so the position starts there rather than
    ending there.
    """
    position = _position(book, "TST-BOND-2030")

    assert position["position_status"] == PositionStatus.OPEN.value
    assert position["net_notional"] == 1_000_000_000


def test_no_rates_or_credit_position_is_ever_closed_by_settlement(book):
    non_fx = book.positions[book.positions["asset_class"] != "FX"]

    assert (non_fx["position_status"] == PositionStatus.OPEN.value).all()


def test_settled_fx_spot_is_closed(book):
    """FIX-008 settled on 2026-07-29: the cash moved, nothing remains to mark."""
    position = _position(book, "EURUSD")

    assert position["position_status"] == PositionStatus.SETTLED.value


def test_settled_fx_spot_still_marked_live_is_reported(book):
    issues = _issues_for(book, IssueCode.SETTLED_TRADE_MARKED_LIVE)

    assert [issue.entity_id for issue in issues] == ["FIX-008"]
    assert issues[0].severity == Severity.WARNING
    assert "LIVE" in issues[0].detail


def test_ndf_is_closed_on_maturity_not_on_its_spot_leg(book):
    """FIX-009 settles T+2 on 2026-07-31 but runs to 2026-08-29.

    Closing it on settle_date would retire a live contract a month early and
    drop its delta from the FX book.
    """
    position = _position(book, "USDCNH")

    assert position["position_status"] == PositionStatus.OPEN.value
    assert position["maturity_date"] == pd.Timestamp("2026-08-29")


def test_term_fx_settle_convention_is_reported(book):
    issues = _issues_for(book, IssueCode.TERM_FX_SETTLE_BEFORE_MATURITY)

    assert [issue.entity_id for issue in issues] == ["FIX-009"]
    assert "spot leg" in issues[0].detail


def test_matured_ndf_reports_its_maturity_not_its_spot_leg(cleaned):
    """Regression: the closing date quoted must be the one that actually closed it.

    No trade in the extract is a matured forward, so this case is unreachable
    from the data -- and would otherwise print the T+2 spot leg, a month off,
    or blank out entirely when settle_date is null.
    """
    matured = cleaned[cleaned["trade_id"] == "FIX-009"].copy()
    matured["maturity_date"] = pd.Timestamp("2026-08-01")

    book = build_positions(matured, as_of=AS_OF)
    issues = _issues_for(book, IssueCode.SETTLED_TRADE_MARKED_LIVE)

    assert _position(book, "USDCNH")["position_status"] == PositionStatus.SETTLED.value
    assert "2026-08-01" in issues[0].detail
    assert "2026-07-31" not in issues[0].detail


def test_forward_whose_settle_equals_maturity_is_not_flagged(book):
    """FIX-003 is a well-formed forward: settle_date == maturity_date."""
    issues = _issues_for(book, IssueCode.TERM_FX_SETTLE_BEFORE_MATURITY)
    flagged = {issue.entity_id for issue in issues}

    assert "FIX-003" not in flagged
    assert _position(book, "USDSGD")["position_status"] == PositionStatus.OPEN.value


def test_fx_spot_without_settle_date_is_kept_open_and_escalated(book):
    """FIX-007 has no settle_date but its maturity has passed.

    The evidence says it settled; the documented rule keys on settle_date. We
    follow the rule and escalate rather than silently retiring the position.
    """
    position = _position(book, "USDJPY")
    issues = _issues_for(book, IssueCode.SETTLEMENT_STATE_UNKNOWN)

    assert position["position_status"] == PositionStatus.OPEN.value
    assert [issue.entity_id for issue in issues] == ["FIX-007"]
    assert issues[0].severity == Severity.ERROR


# --- netting -----------------------------------------------------------------


def test_offsetting_futures_net_despite_differing_descriptions(book):
    """FIX-004 buys 10 and FIX-006 sells 5 of the same contract.

    The blotter describes the short leg as "... Sep26 short", so grouping on
    the description would report two half-positions instead of one net long.
    """
    position = _position(book, "NKY-FUT-2026-09")

    assert position["net_quantity"] == 5
    assert position["gross_quantity"] == 15
    assert position["trade_count"] == 2
    assert position["trade_ids"] == ["FIX-004", "FIX-006"]


def test_fx_spot_and_forward_on_one_pair_stay_separate(cleaned):
    """instrument_id is just the currency pair, shared across tenors."""
    spot = cleaned[cleaned["trade_id"] == "FIX-008"].copy()
    forward = spot.copy()
    forward["trade_id"] = "FIX-008F"
    forward["product_type"] = "FX_FORWARD"
    forward["settle_date"] = pd.Timestamp("2026-09-01")
    forward["maturity_date"] = pd.Timestamp("2026-09-01")

    book = build_positions(pd.concat([cleaned, forward], ignore_index=True), as_of=AS_OF)
    eurusd = book.positions[book.positions["instrument_id"] == "EURUSD"]

    assert len(eurusd) == 2
    assert set(eurusd["product_type"]) == {"FX_SPOT", "FX_FORWARD"}
    assert set(eurusd["position_status"]) == {
        PositionStatus.SETTLED.value,
        PositionStatus.OPEN.value,
    }


def test_short_position_keeps_its_sign(cleaned):
    only_short = cleaned[cleaned["trade_id"] == "FIX-006"]
    book = build_positions(only_short, as_of=AS_OF)

    assert book.positions.iloc[0]["net_quantity"] == -5


def test_every_trade_lands_in_exactly_one_position(book, cleaned):
    booked = [tid for ids in book.positions["trade_ids"] for tid in ids]

    assert sorted(booked) == sorted(cleaned["trade_id"])
    assert len(booked) == len(set(booked))


# --- as-of replay ------------------------------------------------------------


def test_trades_booked_after_the_as_of_date_are_excluded(cleaned):
    """The same engine has to replay any business day of the month."""
    book = build_positions(cleaned, as_of=date(2026, 7, 2))
    booked = [tid for ids in book.positions["trade_ids"] for tid in ids]

    assert sorted(booked) == ["FIX-001", "FIX-002"]


def test_a_position_open_in_july_is_settled_by_august(cleaned):
    """FIX-008 settles on 2026-07-29, so its status depends on the as-of date."""
    july = build_positions(cleaned, as_of=date(2026, 7, 28))
    august = build_positions(cleaned, as_of=AS_OF)

    assert _position(july, "EURUSD")["position_status"] == PositionStatus.OPEN.value
    assert _position(august, "EURUSD")["position_status"] == PositionStatus.SETTLED.value


def test_settlement_boundary_is_exclusive(cleaned):
    """A trade settling *on* the as-of date is still open that morning."""
    on_settlement_day = build_positions(cleaned, as_of=date(2026, 7, 29))

    assert _position(on_settlement_day, "EURUSD")["position_status"] == PositionStatus.OPEN.value


def test_empty_book_is_handled(cleaned):
    book = build_positions(cleaned, as_of=date(2026, 1, 1))

    assert book.positions.empty
    assert book.issues == []


def test_every_position_satisfies_the_published_schema(book):
    """The Position model is the API contract; prove the engine actually meets it."""
    for record in to_records(book.positions):
        Position.model_validate(record)


def test_settled_and_open_exposure_can_be_told_apart(book):
    """The whole point of the status: an open-FX figure that excludes settled cash."""
    fx = book.positions[book.positions["asset_class"] == "FX"]
    open_fx = fx[fx["position_status"] == PositionStatus.OPEN.value]

    assert len(open_fx) < len(fx)
    assert "FIX-008" not in {tid for ids in open_fx["trade_ids"] for tid in ids}
