"""FX conversion tests.

The whole point of this module is that using the wrong quoting convention is
silent: no exception, no warning, just a number that is off by a factor of 150
and still prints plausibly. So the tests pin the direction explicitly in both
conventions rather than trusting a round trip to catch it.
"""

from datetime import date

import pytest

from app.dq import clean_trades
from app.fx import FxRates
from app.loaders import load_fx_rates_raw, load_trades_raw

AS_OF = date(2026, 8, 5)


@pytest.fixture
def rates():
    return FxRates(load_fx_rates_raw())


def test_usd_is_returned_untouched(rates):
    assert rates.to_usd(1_234.56, "USD", AS_OF) == 1_234.56


def test_quote_currency_is_divided(rates):
    """USDJPY = 150.00 means 150 JPY per USD, so JPY must be divided."""
    assert rates.to_usd(150_000, "JPY", AS_OF) == pytest.approx(1_000.0)


def test_base_currency_is_multiplied(rates):
    """EURUSD = 1.0890 means 1.089 USD per EUR, so EUR must be multiplied."""
    assert rates.to_usd(1_000, "EUR", AS_OF) == pytest.approx(1_089.0)


def test_the_two_conventions_are_not_interchangeable(rates):
    """The failure this module exists to prevent, stated as an assertion.

    Inverting the direction on JPY is a factor of 22,500 -- and on EUR the
    result would still look like a believable number, which is worse.
    """
    jpy_correct = rates.to_usd(150_000, "JPY", AS_OF)
    jpy_inverted = 150_000 * rates.rate("USDJPY", AS_OF)

    assert jpy_correct == pytest.approx(1_000.0)
    assert jpy_inverted / jpy_correct == pytest.approx(150.0**2)


def test_every_traded_currency_can_be_converted(rates):
    """A currency the desk trades but cannot report is a hole in the P&L.

    Derived from the blotter rather than hard-coded, so the invariant holds
    against the real extract and the fixture alike.
    """
    traded = set(clean_trades(load_trades_raw()).trades["currency"])

    assert traded <= set(rates.currencies)
    for currency in traded:
        assert rates.to_usd(1_000, currency, AS_OF) > 0


def test_conversion_direction_matches_the_declared_pair(rates):
    """Derive the expected direction from the file's own base/quote columns."""
    frame = load_fx_rates_raw()
    same_day = frame[frame["date"].dt.date == AS_OF]

    for row in same_day.itertuples(index=False):
        if row.base_ccy == "USD":
            expected = 1_000 / row.spot_rate
            assert rates.to_usd(1_000, row.quote_ccy, AS_OF) == pytest.approx(expected)
        else:
            expected = 1_000 * row.spot_rate
            assert rates.to_usd(1_000, row.base_ccy, AS_OF) == pytest.approx(expected)


def test_unknown_currency_raises_rather_than_passing_through(rates):
    """Returning the amount unconverted would silently report GBP as USD."""
    with pytest.raises(KeyError, match="No USD pair available"):
        rates.to_usd(1_000, "GBP", AS_OF)


def test_missing_date_is_refused_rather_than_carried_forward(rates):
    """A stale rate silently reused is worse than an explicit failure."""
    with pytest.raises(KeyError, match="No FX rates at all"):
        rates.to_usd(1_000, "JPY", date(2026, 8, 6))


def test_rates_move_day_to_day(rates):
    """Guard against the lookup collapsing onto a single date."""
    assert rates.rate("USDJPY", date(2026, 8, 4)) != rates.rate("USDJPY", AS_OF)


def test_dates_are_exposed_in_order(rates):
    assert rates.dates == sorted(rates.dates)
    assert len(rates.dates) > 1
