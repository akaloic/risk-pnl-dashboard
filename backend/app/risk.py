"""Sensitivities aggregated by book and metric.

Two rules decide what this grid is allowed to add up.

*Only additive metrics are summed.* DV01, CS01, delta and the rest are amounts
and add across trades. Duration is quoted in years: adding the durations of two
swaps produces a number with no meaning at all, so tenors are reported per
trade and never totalled.

*Settled trades are excluded from open risk, and the exclusion is stated.* The
risk file still publishes delta for FX spots that have already settled -- 19.4m
USD of it on this extract. Leaving it in overstates what the desk is actually
exposed to; dropping it silently would leave a risk manager wondering where the
number went. Both figures are therefore carried side by side.
"""

from datetime import date

import pandas as pd
from pydantic import BaseModel

from app.config import AS_OF_DATE
from app.dataset import Dataset
from app.positions import settled_trade_ids

# Units that represent an amount of money, and so may be added together.
_ADDITIVE_UNITS = {"amount", "amount_usd"}


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
