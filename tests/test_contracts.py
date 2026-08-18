"""Contract multiplier tests.

The central test re-derives the multiplier from the fixture's risk file the
same way it was recovered from the real one, so the constant is checked
against an independent identity rather than merely asserted equal to itself.
"""

import pandas as pd
import pytest

from app.contracts import CONTRACT_MULTIPLIERS, multiplier_for
from app.dq import clean_trades
from app.loaders import (
    load_fx_rates_raw,
    load_market_data_raw,
    load_risk_sensitivities_raw,
    load_trades_raw,
)

AS_OF = pd.Timestamp("2026-08-05")


def test_multiplier_lookup_by_underlying():
    assert multiplier_for("NKY-FUT-2026-09") == 1_000
    assert multiplier_for("NKY-CALL-38000-2026-09") == 1_000
    assert multiplier_for("HSI-PUT-18000-2026-09") == 50
    assert multiplier_for("KOSPI200-FUT-2026-09") == 250


def test_unknown_underlying_raises_rather_than_defaulting():
    """A default of 1.0 would price a Nikkei future at a thousandth of its size.

    The wrong number would still look plausible on screen, which is precisely
    what makes a silent default dangerous here.
    """
    with pytest.raises(KeyError, match="No contract multiplier configured"):
        multiplier_for("SPX-FUT-2026-09")


def test_multiplier_is_recoverable_from_the_risk_file():
    """Re-derive the multiplier from Delta_USD = qty x mult x price / fx.

    This is the identity the real multipliers were recovered from. The fixture
    encodes it for FIX-004: 10 contracts at 38,500 with a 150.00 USDJPY gives
    a delta of 2,566,666.67 USD if and only if the multiplier is 1,000.
    """
    trades = clean_trades(load_trades_raw()).trades.set_index("trade_id")
    quotes = load_market_data_raw()
    rates = load_fx_rates_raw()
    risk = load_risk_sensitivities_raw()

    trade = trades.loc["FIX-004"]
    price = quotes[
        (quotes["instrument_id"] == trade["instrument_id"]) & (quotes["date"] == AS_OF)
    ]["px_mid"].iloc[0]
    fx = rates[(rates["ccy_pair"] == "USDJPY") & (rates["date"] == AS_OF)]["spot_rate"].iloc[0]
    delta_usd = risk[(risk["trade_id"] == "FIX-004") & (risk["risk_metric"] == "Delta_USD")][
        "value_usd"
    ].iloc[0]

    signed_quantity = trade["quantity"] * trade["direction_sign"]
    implied = delta_usd * fx / (signed_quantity * price)

    assert implied == pytest.approx(multiplier_for(trade["instrument_id"]), rel=1e-6)


def test_short_leg_derives_the_same_multiplier():
    """The identity must hold on a short position too, or the sign is wrong."""
    trades = clean_trades(load_trades_raw()).trades.set_index("trade_id")
    quotes = load_market_data_raw()
    rates = load_fx_rates_raw()
    risk = load_risk_sensitivities_raw()

    trade = trades.loc["FIX-006"]
    price = quotes[
        (quotes["instrument_id"] == trade["instrument_id"]) & (quotes["date"] == AS_OF)
    ]["px_mid"].iloc[0]
    fx = rates[(rates["ccy_pair"] == "USDJPY") & (rates["date"] == AS_OF)]["spot_rate"].iloc[0]
    delta_usd = risk[(risk["trade_id"] == "FIX-006") & (risk["risk_metric"] == "Delta_USD")][
        "value_usd"
    ].iloc[0]

    signed_quantity = trade["quantity"] * trade["direction_sign"]
    implied = delta_usd * fx / (signed_quantity * price)

    assert signed_quantity == -5
    assert implied == pytest.approx(1_000, rel=1e-6)


def test_a_wrong_multiplier_is_off_by_orders_of_magnitude():
    """Why this warrants its own module: the failure mode is not subtle."""
    quantity, price = 10, 38_500

    correct = quantity * multiplier_for("NKY-FUT-2026-09") * price
    if_defaulted_to_one = quantity * 1 * price

    assert correct / if_defaulted_to_one == 1_000


def test_every_configured_multiplier_is_positive():
    assert all(value > 0 for value in CONTRACT_MULTIPLIERS.values())


def test_hsi_multiplier_is_bounded_below_by_the_delta_constraint():
    """The one multiplier that could not be derived, so its claim is pinned here.

    With no Hang Seng future in the blotter the identity cannot be inverted.
    What the option delta *does* prove is a lower bound: a call delta above 1
    is impossible, so any multiplier at or below 25 is ruled out. 50 survives;
    so would 100, which is why the module calls this corroboration rather than
    derivation.
    """
    quantity, index_level, fx = 50, 18_339.9747, 7.8115
    delta_usd = 3_418_357.5498  # HSI call, as carried by the risk file

    def implied_option_delta(multiplier):
        return delta_usd * fx / (quantity * multiplier * index_level)

    assert implied_option_delta(25) > 1
    assert implied_option_delta(50) == pytest.approx(0.58, abs=0.01)
    assert abs(implied_option_delta(CONTRACT_MULTIPLIERS["HSI"])) <= 1
