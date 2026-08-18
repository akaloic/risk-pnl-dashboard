"""Conversion into the reporting currency.

USD is the reporting currency, and every figure the desk sees passes through
here. The reason this is a module of its own rather than a line of arithmetic
repeated per product is that the extract mixes the two quoting conventions:

    USDJPY, USDCNH, USDSGD, USDKRW, USDHKD   USD is the base -> divide
    EURUSD, AUDUSD                            USD is the quote -> multiply

Applying the wrong one does not raise, does not warn, and does not look wrong
on a screen. A JPY figure converted the wrong way is off by a factor of 150 and
an EUR figure by 1.19, both of which still print as a plausible number. So the
direction is derived from the base_ccy/quote_ccy columns rather than assumed
from the pair name, and it is pinned by tests in both directions.
"""

from datetime import date

import pandas as pd

from app.config import REPORTING_CCY


class FxRates:
    """Point lookup over the daily spot grid.

    Built once and queried per trade: the daily P&L replay values the whole
    book on every business day of the month, so a linear scan of the rate
    frame per conversion would be the wrong shape entirely.
    """

    def __init__(self, frame: pd.DataFrame):
        self._rates: dict[tuple[pd.Timestamp, str], float] = {
            (row.date, row.ccy_pair): float(row.spot_rate)
            for row in frame.itertuples(index=False)
        }
        self._conversions = self._map_currencies(frame)
        self._dates = frozenset(frame["date"].unique())
        self._pair_currencies: dict[str, tuple[str, str]] = {
            row.ccy_pair: (row.base_ccy, row.quote_ccy)
            for row in frame[["ccy_pair", "base_ccy", "quote_ccy"]]
            .drop_duplicates()
            .itertuples(index=False)
        }

    @staticmethod
    def _map_currencies(frame: pd.DataFrame) -> dict[str, tuple[str, bool]]:
        """Map each foreign currency to its pair and which way the rate applies.

        The bool is True when the rate must be divided into the amount, i.e.
        when the quote is "units of this currency per USD".
        """
        conversions: dict[str, tuple[str, bool]] = {}

        for pair, base, quote in (
            frame[["ccy_pair", "base_ccy", "quote_ccy"]].drop_duplicates().itertuples(index=False)
        ):
            if quote == REPORTING_CCY:
                foreign, divide = base, False
            elif base == REPORTING_CCY:
                foreign, divide = quote, True
            else:
                # A cross pair carries no USD leg, so it cannot convert on its
                # own. None appear in this extract; refuse rather than guess a
                # triangulation the desk has not asked for.
                continue

            existing = conversions.get(foreign)
            if existing and existing != (pair, divide):
                raise ValueError(
                    f"{foreign} is quoted by two conflicting pairs: {existing[0]} and {pair}"
                )
            conversions[foreign] = (pair, divide)

        return conversions

    def pair_currencies(self, ccy_pair: str) -> tuple[str, str]:
        """The (base, quote) currencies of a pair.

        FX P&L accrues in the quote currency -- a USDJPY position earns or
        loses yen -- so pricing needs to know which side is which rather than
        assuming the trade currency is the one the profit lands in.
        """
        try:
            return self._pair_currencies[ccy_pair]
        except KeyError:
            raise KeyError(
                f"{ccy_pair} is not in the FX extract. Known pairs: "
                f"{sorted(self._pair_currencies)}"
            ) from None

    def rate(self, ccy_pair: str, on: date) -> float:
        """Spot rate for `ccy_pair` on `on`, by exact date."""
        key = (pd.Timestamp(on), ccy_pair)
        try:
            return self._rates[key]
        except KeyError:
            if pd.Timestamp(on) not in self._dates:
                raise KeyError(
                    f"No FX rates at all for {on}. The extract covers business days only; "
                    "value the book on a date the desk actually published."
                ) from None
            raise KeyError(f"No {ccy_pair} rate on {on}") from None

    def to_usd(self, amount: float, ccy: str, on: date) -> float:
        """Convert `amount` from `ccy` into USD at the spot rate of `on`.

        No fallback to a neighbouring date: the grid is complete for every
        business day, so a miss means the caller asked for a day the desk did
        not publish, and carrying a stale rate forward silently would be worse
        than saying so.
        """
        if ccy == REPORTING_CCY:
            return float(amount)

        try:
            pair, divide = self._conversions[ccy]
        except KeyError:
            raise KeyError(
                f"No USD pair available to convert {ccy}. Known: "
                f"{sorted(self._conversions)}"
            ) from None

        spot = self.rate(pair, on)
        return float(amount) / spot if divide else float(amount) * spot

    @property
    def dates(self) -> list[pd.Timestamp]:
        """Business days the extract covers, ascending."""
        return sorted(self._dates)

    @property
    def currencies(self) -> list[str]:
        """Currencies convertible into USD, plus USD itself."""
        return sorted({REPORTING_CCY, *self._conversions})
