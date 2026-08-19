"""Sensitivities aggregated by book and metric, and spread along the curve.

Three rules decide what this grid is allowed to add up.

*Only additive metrics are summed.* DV01, CS01, delta and the rest are amounts
and add across trades. Duration is quoted in years: adding the durations of two
swaps produces a number with no meaning at all, so tenors are reported per
trade and never totalled.

*Settled trades are excluded from open risk, and the exclusion is stated.* The
risk file still publishes delta for FX spots that have already settled -- 19.4m
USD of it on this extract. Leaving it in overstates what the desk is actually
exposed to; dropping it silently would leave a risk manager wondering where the
number went. Both figures are therefore carried side by side.

*A total is not a position.* A book-level DV01 says how much the book makes on
a parallel shift and nothing about where on the curve it sits. Two books each
showing 2,268 USD of DV01 are in completely different positions if one is a
five-year point and the other is ten-year against two-year. The same total also
hides a curve trade entirely: a long and a short of equal size net to roughly
nothing at book level while carrying real exposure to the shape of the curve.
So the additive metrics are also reported by tenor bucket.

The tenor comes from the trade's own `maturity_date`, which every row in this
blotter carries, rather than from parsing the instrument id. `JPY-IRS-10Y` and
`TOYOTA-1.5-2030` encode their tenors in two different ways and neither is a
field, so reading the maturity is both simpler and correct for the one product
whose id says nothing at all.
"""

from datetime import date

import pandas as pd
from pydantic import BaseModel

from app.config import AS_OF_DATE
from app.dataset import Dataset
from app.positions import settled_trade_ids

# Units that represent an amount of money, and so may be added together.
_ADDITIVE_UNITS = {"amount", "amount_usd"}

# Curve buckets, in curve order, with an inclusive upper bound in whole
# calendar months: a five-year swap belongs to 3-5Y, not 5-10Y. The order is
# carried as data rather than left to the label, because sorting these as
# strings puts "10Y+" second and hands a risk manager a curve that runs
# 0-3M, 10Y+, 1-3Y.
#
# `None` is the open end. Bounds are walked on the calendar rather than divided
# out of a day count: ten years from 2026-08-05 is 3,653 days, which over
# 365.25 gives 10.0014 and drops a plain 10Y swap into 10Y+. A trade maturing
# on its own anniversary has to land in the bucket that anniversary names.
#
# The front of the curve is split at three months because a single 0-1Y bucket
# was hiding the largest fact about this desk. It held 17 trades maturing
# anywhere from 22 to 309 days out -- the entire FX book and the entire equity
# derivatives book -- and 16 of those 17 fall inside 60 days, carrying 396k USD
# of the desk's 444k loss. A bucket that puts "expires in three weeks" beside
# "expires in eleven months" answers the question it was built to answer and
# still leaves a risk manager blind to the roll-off in front of them.
_TENOR_BUCKETS: tuple[tuple[str, int | None], ...] = (
    ("0-3M", 3),
    ("3-12M", 12),
    ("1-3Y", 36),
    ("3-5Y", 60),
    ("5-10Y", 120),
    ("10Y+", None),
)

# Anything already past its maturity date. It should be empty once settlement
# has been applied, so a figure here is worth seeing rather than rounding into
# the front bucket: on this extract it surfaces TRD-027, the FX spot whose
# settlement could not be confirmed and which is deliberately still open.
_MATURED = "Matured"


def tenor_bucket(maturity: pd.Timestamp, as_of: date) -> str:
    """Which curve bucket a trade maturing on `maturity` belongs to.

    A missing maturity counts as matured rather than as an unknown point: the
    blotter's only rows without one are FX spots whose settlement is already in
    question, and putting them on the curve would be inventing a tenor.
    """
    if pd.isna(maturity):
        return _MATURED

    today = pd.Timestamp(as_of)
    if maturity <= today:
        return _MATURED

    for label, months in _TENOR_BUCKETS:
        if months is None or maturity <= today + pd.DateOffset(months=months):
            return label
    raise AssertionError("the last bucket is open-ended, so the loop always returns")


def _bucket_order(label: str) -> int:
    """Position along the curve, so the grid never sorts 10Y+ next to 0-3M."""
    labels = [_MATURED, *(label for label, _ in _TENOR_BUCKETS)]
    return labels.index(label)


class RiskAggregate(BaseModel):
    """One book's exposure to one risk metric, in USD.

    `open_usd` is the live exposure and the figure to act on. `settled_usd` is
    what the risk file still carries for trades that have closed, kept visible
    rather than dropped so the difference can be challenged.
    """

    book_id: str
    risk_metric: str
    open_usd: float
    settled_usd: float
    total_usd: float
    trade_count: int


def aggregate_risk(data: Dataset, as_of: date = AS_OF_DATE) -> pd.DataFrame:
    """Sum the additive sensitivities by book and metric, in USD."""
    additive = data.risk[data.risk["unit"].isin(_ADDITIVE_UNITS)].copy()

    settled = settled_trade_ids(data.trades, as_of=as_of)

    additive["is_settled"] = additive["trade_id"].isin(settled)
    additive["open_usd"] = additive["value_usd"].where(~additive["is_settled"], 0.0)
    additive["settled_usd"] = additive["value_usd"].where(additive["is_settled"], 0.0)

    return (
        additive.groupby(["book_id", "risk_metric"])
        .agg(
            open_usd=("open_usd", "sum"),
            settled_usd=("settled_usd", "sum"),
            total_usd=("value_usd", "sum"),
            trade_count=("trade_id", "nunique"),
        )
        .reset_index()
        .sort_values(["book_id", "risk_metric"])
        .reset_index(drop=True)
    )


class TenorExposure(BaseModel):
    """One book's exposure to one metric at one point on the curve, in USD."""

    book_id: str
    risk_metric: str
    tenor_bucket: str
    open_usd: float
    trade_count: int


def risk_by_tenor(data: Dataset, as_of: date = AS_OF_DATE) -> pd.DataFrame:
    """Spread the open additive sensitivities across curve buckets.

    Open risk only. Bucketing settled exposure by tenor would be answering
    where on the curve a position sits that no longer exists; the settled
    figure stays in the book-level grid, where it is a data quality finding
    rather than a position.
    """
    additive = data.risk[data.risk["unit"].isin(_ADDITIVE_UNITS)]
    settled = settled_trade_ids(data.trades, as_of=as_of)
    live = additive[~additive["trade_id"].isin(settled)].copy()

    maturities = data.trades.drop_duplicates("trade_id").set_index("trade_id")["maturity_date"]
    live["tenor_bucket"] = (
        live["trade_id"].map(maturities).map(lambda maturity: tenor_bucket(maturity, as_of))
    )

    grid = (
        live.groupby(["book_id", "risk_metric", "tenor_bucket"])
        .agg(open_usd=("value_usd", "sum"), trade_count=("trade_id", "nunique"))
        .reset_index()
    )
    grid["_order"] = grid["tenor_bucket"].map(_bucket_order)

    return (
        grid.sort_values(["book_id", "risk_metric", "_order"])
        .drop(columns="_order")
        .reset_index(drop=True)
    )


def non_additive_metrics(data: Dataset) -> pd.DataFrame:
    """Per-trade tenor figures, reported rather than summed.

    Kept out of the grid above on purpose: a total duration is not a quantity
    that exists.
    """
    return (
        data.risk[~data.risk["unit"].isin(_ADDITIVE_UNITS)][
            ["book_id", "trade_id", "instrument_id", "risk_metric", "value", "unit"]
        ]
        .sort_values(["book_id", "trade_id", "risk_metric"])
        .reset_index(drop=True)
    )
