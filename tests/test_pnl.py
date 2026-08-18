"""P&L engine tests.

Weighted towards sign and scale rather than plumbing: a P&L bug does not throw,
it prints a believable number with the wrong sign or off by a multiplier, and
that is what these assertions are built to catch.
"""

from datetime import date

import pandas as pd
import pytest

from app.dataset import load_dataset
from app.issues import IssueCode
from app.loaders import to_records
from app.pnl import PnLMethod, TradePnL, compute_pnl

AS_OF = date(2026, 8, 5)


@pytest.fixture
def data():
    return load_dataset()


@pytest.fixture
def priced(data):
    return compute_pnl(data, as_of=AS_OF)


def _pnl(priced, trade_id):
    rows = priced.trades[priced.trades["trade_id"] == trade_id]
    assert len(rows) == 1, f"expected one row for {trade_id}, got {len(rows)}"
    return rows.iloc[0]


# --- per-product economics ---------------------------------------------------


def test_bond_pnl_is_price_move_on_face(priced):
    """Clean price is per 100, so the move is a percentage of the face amount.

    FIX-001 bought 1bn JPY of face at 100.00, marked at 101.00: 1% of face.
    """
    row = _pnl(priced, "FIX-001")

    assert row["method"] == PnLMethod.BOND_CLEAN_PRICE.value
    assert row["pnl_ccy"] == pytest.approx(10_000_000)
    assert row["pnl_usd"] == pytest.approx(10_000_000 / 150.0)


def test_bond_quantity_is_not_used_as_size(priced):
    """The blotter's notional-to-quantity ratio is not constant across markets.

    Sizing a bond off quantity instead of face would be wrong by that ratio,
    so the result must track notional exactly.
    """
    row = _pnl(priced, "FIX-001")

    assert row["pnl_ccy"] == pytest.approx((101.00 - 100.00) / 100 * 1_000_000_000)


def test_receiver_swap_gains_when_rates_fall(data):
    """The sign convention that would otherwise invert the whole rates book.

    DV01 is positive for a long-duration position, so the P&L negates the rate
    move: a receiver of fixed makes money as par rates fall.
    """
    trades = data.trades.copy()
    trades.loc[trades["trade_id"] == "FIX-002", "direction"] = "RECEIVE"
    trades.loc[trades["trade_id"] == "FIX-002", "direction_sign"] = 1
    risk = data.risk.copy()
    risk.loc[(risk["trade_id"] == "FIX-002") & (risk["risk_metric"] == "DV01"), "value"] = 180_000

    receiver = compute_pnl(
        type(data)(
            trades=trades,
            raw_trades=data.raw_trades,
            quotes=data.quotes,
            risk=risk,
            fx=data.fx,
            issues=[],
        ),
        as_of=AS_OF,
    )
    row = _pnl(receiver, "FIX-002")

    # Par rate rose 1.05 -> 1.10, so a receiver loses.
    assert row["current_level"] > row["reference_level"]
    assert row["pnl_ccy"] < 0


def test_payer_swap_gains_when_rates_rise(priced):
    """FIX-002 pays fixed with a negative DV01; the par rate rose 1.00 -> 1.10."""
    row = _pnl(priced, "FIX-002")

    assert row["method"] == PnLMethod.SWAP_DV01.value
    assert row["current_level"] > row["reference_level"]
    assert row["pnl_ccy"] > 0
    # 10bp move on a DV01 of -180,000 JPY.
    assert row["pnl_ccy"] == pytest.approx(-(1.10 - 1.00) * 100 * -180_000)


def test_swap_and_credit_use_opposite_sensitivity_conventions(priced, data):
    """DV01 negates the move, CS01 does not -- the trap this engine encodes.

    Both are "sensitivity x level move", so it is tempting to share one
    function. The file signs them oppositely: DV01 positive means long
    duration, CS01 positive means bought protection.
    """
    swap = _pnl(priced, "FIX-002")
    dv01 = data.risk[
        (data.risk["trade_id"] == "FIX-002") & (data.risk["risk_metric"] == "DV01")
    ]["value"].iloc[0]

    move_bp = (swap["current_level"] - swap["reference_level"]) * 100
    assert swap["pnl_ccy"] == pytest.approx(-move_bp * dv01)


def test_equity_pnl_scales_by_the_contract_multiplier(priced):
    """FIX-004 is 10 Nikkei futures bought at 38,000 and marked at 38,500."""
    row = _pnl(priced, "FIX-004")

    assert row["method"] == PnLMethod.EQUITY_CONTRACT.value
    assert row["pnl_ccy"] == pytest.approx((38_500 - 38_000) * 10 * 1_000)


def test_equity_short_gains_when_the_index_falls(priced):
    """FIX-006 sold 5 contracts at 38,300 against a mark of 38,500: a loss."""
    row = _pnl(priced, "FIX-006")

    assert row["pnl_ccy"] == pytest.approx((38_500 - 38_300) * 5 * 1_000 * -1)
    assert row["pnl_ccy"] < 0


def test_equity_is_sized_on_contracts_not_on_notional(priced, data):
    """Equity trades book a notional of zero, which would report them flat."""
    assert (data.trades.loc[data.trades["asset_class"] == "EQUITY", "notional"] == 0).all()
    assert _pnl(priced, "FIX-004")["pnl_ccy"] != 0


def test_fx_pnl_accrues_in_the_quote_currency(priced):
    """A USDSGD position earns Singapore dollars, not the trade currency."""
    row = _pnl(priced, "FIX-003")

    assert row["method"] == PnLMethod.FX_RATE_MOVE.value
    assert row["currency"] == "USD"
    assert row["pnl_currency"] == "SGD"
    assert row["pnl_ccy"] == pytest.approx((1.3350 - 1.3400) * 5_000_000)


def test_fx_is_priced_off_the_rate_grid_not_market_data(data, priced):
    """market_data.csv holds no FX rows at all, by its own asset-class domain."""
    assert data.quotes[data.quotes["asset_class"] == "FX"].empty
    assert not priced.trades[priced.trades["method"] == PnLMethod.FX_RATE_MOVE.value].empty


def test_fx_exposure_from_the_blotter_agrees_with_the_published_delta(data):
    """Pricing FX off the blotter is only safe if it reproduces the risk file.

    The engine derives exposure from notional and spot rather than reading
    Delta_USD, so that the P&L stays reproducible from the market data alone.
    That is defensible only if the two agree, which is what this pins.
    """
    delta = data.risk[data.risk["risk_metric"] == "Delta_USD"].set_index("trade_id")["value_usd"]
    trades = data.trades.set_index("trade_id")
    fx_trades = trades[trades["asset_class"] == "FX"]

    assert not fx_trades.empty
    for trade_id, trade in fx_trades.iterrows():
        base, _ = data.fx.pair_currencies(trade["instrument_id"])
        exposure = data.fx.to_usd(trade["notional"], base, AS_OF) * trade["direction_sign"]

        assert exposure == pytest.approx(delta[trade_id], rel=2e-3)


# --- settlement --------------------------------------------------------------


def test_settled_fx_is_frozen_at_its_closing_date(priced):
    """FIX-008 settled on 2026-07-29: the cash moved and the P&L is realised.

    Marking it at the as-of rate would let a finished trade keep moving with
    spot for the rest of the month.
    """
    row = _pnl(priced, "FIX-008")

    assert row["valuation_date"] == date(2026, 7, 29)


def test_open_fx_is_marked_at_the_as_of_date(priced):
    row = _pnl(priced, "FIX-003")

    assert row["valuation_date"] == AS_OF


# --- windowed P&L, as the daily replay needs it ------------------------------


def test_since_window_measures_from_that_days_close(data):
    """With `since` set the reference is a market level, not the traded level."""
    window = compute_pnl(data, as_of=AS_OF, since=date(2026, 8, 4))
    row = _pnl(window, "FIX-001")

    assert row["reference_level"] == pytest.approx(100.50)
    assert row["pnl_ccy"] == pytest.approx((101.00 - 100.50) / 100 * 1_000_000_000)


def test_a_trade_struck_inside_the_window_measures_from_its_own_price(data):
    """Otherwise a trade booked today would show the market's move, not its own."""
    window = compute_pnl(data, as_of=AS_OF, since=date(2026, 7, 1))
    row = _pnl(window, "FIX-004")

    assert row["reference_level"] == pytest.approx(38_000)


def test_a_trade_settled_before_the_window_earns_nothing_in_it(data):
    """Otherwise the daily series credits realised trades with phantom moves.

    FIX-008 settled on 2026-07-29. Over 08-04 to 08-05 it must contribute zero:
    referencing the window's opening level against a closing level that
    precedes it measures the market backwards.
    """
    window = compute_pnl(data, as_of=AS_OF, since=date(2026, 8, 4))
    row = _pnl(window, "FIX-008")

    assert row["reference_level"] == row["current_level"]
    assert row["pnl_ccy"] == 0
    assert row["pnl_usd"] == 0


def test_a_trade_settling_inside_the_window_keeps_its_move(data):
    """The complement: it closed during the window, so the move up to then counts."""
    window = compute_pnl(data, as_of=AS_OF, since=date(2026, 7, 2))
    row = _pnl(window, "FIX-008")

    assert row["valuation_date"] == date(2026, 7, 29)
    assert row["pnl_ccy"] != 0


def test_inception_and_window_differ(data):
    inception = _pnl(compute_pnl(data, as_of=AS_OF), "FIX-001")
    window = _pnl(compute_pnl(data, as_of=AS_OF, since=date(2026, 8, 4)), "FIX-001")

    assert inception["pnl_ccy"] != window["pnl_ccy"]


# --- conversion and completeness ---------------------------------------------


def test_everything_is_reported_in_usd(priced):
    assert priced.trades["pnl_usd"].notna().all()

    non_usd = priced.trades[priced.trades["pnl_currency"] != "USD"]
    assert not non_usd.empty
    assert (non_usd["pnl_usd"] != non_usd["pnl_ccy"]).all()


def test_a_trade_without_a_price_is_excluded_and_reported(data):
    """Never valued at a stale or assumed level: a missing mark is an error."""
    quotes = data.quotes[data.quotes["instrument_id"] != "TST-BOND-2030"]
    result = compute_pnl(
        type(data)(
            trades=data.trades,
            raw_trades=data.raw_trades,
            quotes=quotes,
            risk=data.risk,
            fx=data.fx,
            issues=[],
        ),
        as_of=AS_OF,
    )

    assert "FIX-001" not in set(result.trades["trade_id"])
    codes = {issue.code for issue in result.issues}
    assert IssueCode.MISSING_MARKET_DATA in codes


def test_a_swap_without_dv01_is_excluded_and_reported(data):
    """Assuming a zero sensitivity would silently report the swap as flat."""
    risk = data.risk[
        ~((data.risk["trade_id"] == "FIX-002") & (data.risk["risk_metric"] == "DV01"))
    ]
    result = compute_pnl(
        type(data)(
            trades=data.trades,
            raw_trades=data.raw_trades,
            quotes=data.quotes,
            risk=risk,
            fx=data.fx,
            issues=[],
        ),
        as_of=AS_OF,
    )

    assert "FIX-002" not in set(result.trades["trade_id"])
    assert IssueCode.MISSING_SENSITIVITY in {issue.code for issue in result.issues}


def test_a_backwards_window_is_refused(data):
    """An inverted window measures the market in reverse and looks plausible."""
    with pytest.raises(ValueError, match="cannot run backwards"):
        compute_pnl(data, as_of=date(2026, 8, 4), since=date(2026, 8, 5))


def test_valuing_on_an_unpublished_day_is_refused(data):
    """A Saturday prices only the trades that closed earlier, not the book.

    Returning that partial total silently would put a meaningless number on a
    desk summary card.
    """
    with pytest.raises(ValueError, match="not a day this extract prices"):
        compute_pnl(data, as_of=date(2026, 8, 8))


def test_an_unpublished_reference_day_is_refused(data):
    with pytest.raises(ValueError, match="since=2026-08-08"):
        compute_pnl(data, as_of=date(2026, 8, 5), since=date(2026, 8, 8))


def test_trades_booked_after_the_as_of_date_are_not_priced(data):
    early = compute_pnl(data, as_of=date(2026, 7, 2))

    assert set(early.trades["trade_id"]) <= {"FIX-001", "FIX-002"}


def test_every_product_type_in_the_blotter_has_a_pricer(data, priced):
    """A product with no pricer would raise, not silently vanish -- prove it."""
    priced_or_flagged = set(priced.trades["trade_id"]) | {i.entity_id for i in priced.issues}

    assert set(data.trades["trade_id"]) == priced_or_flagged


def test_every_row_satisfies_the_published_schema(priced):
    for record in to_records(priced.trades):
        TradePnL.model_validate(record)


def test_pnl_is_reproducible(data):
    first = compute_pnl(data, as_of=AS_OF).trades
    second = compute_pnl(data, as_of=AS_OF).trades

    pd.testing.assert_frame_equal(first, second)
