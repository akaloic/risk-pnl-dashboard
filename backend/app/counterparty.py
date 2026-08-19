"""Who the desk is facing, and what it would lose if they stopped paying.

Three different questions get three different answers on this book, and running
them together is the mistake this module exists to avoid.

*Notional is the size of a relationship, not an exposure.* A 10m USD forward
against Citi is 10m of business and, on this extract, nothing at risk: the trade
is marked in the desk's favour by less than nothing, so a default costs the desk
no money. Exposure is what the counterparty owes, which is the mark to market
where it is positive and zero where it is not. Reporting the two as one figure
would have the desk manage the wrong number.

*Notional has to be converted before it is compared.* The blotter mixes JPY,
KRW, HKD and USD notionals in one column, and adding them as they stand ranks
counterparties by the size of their currency's units. Summed raw, KB Securities
is 61% of the desk's book and first by a distance; converted to USD it is 9.4%
and sixth. That is not a rounding difference, it is a different list, and the
raw one would send a credit officer to the wrong counterparty.

*A settled trade has no counterparty.* The cash was exchanged, so nothing is
owed either way. Settled trades stay counted, separately, because a
relationship's size is a fact about the desk even after the trades close.
"""

from datetime import date

import pandas as pd
from pydantic import BaseModel

from app.config import AS_OF_DATE
from app.dataset import Dataset
from app.pnl import compute_pnl
from app.positions import settled_trade_ids


class CounterpartyExposure(BaseModel):
    """One counterparty's standing with the desk, in USD.

    `current_exposure_usd` is the figure a credit officer acts on: the sum of
    the marks that are in the desk's favour, which is what a default would cost.
    `net_mtm_usd` is the whole relationship including what the desk owes back,
    and can be negative -- useful for context, misleading as a credit limit.
    """

    counterparty_id: str
    counterparty_name: str
    open_trades: int
    settled_trades: int
    books: int
    gross_notional_usd: float
    current_exposure_usd: float
    net_mtm_usd: float
    share_of_exposure_pct: float


def exposure_by_counterparty(data: Dataset, as_of: date = AS_OF_DATE) -> pd.DataFrame:
    """Rank the desk's counterparties by what a default would actually cost.

    Trades the pricing engine could not mark are counted in the trade and
    notional columns but contribute nothing to exposure: they are excluded from
    P&L with an error rather than valued at an assumed level, and inventing a
    zero here would quietly understate a relationship instead.
    """
    priced, _ = compute_pnl(data, as_of=as_of)
    marks = dict(zip(priced["trade_id"], priced["pnl_usd"], strict=True))
    settled = settled_trade_ids(data.trades, as_of=as_of)

    trades = data.trades.copy()
    trades["is_settled"] = trades["trade_id"].isin(settled)
    trades["mark_usd"] = trades["trade_id"].map(marks).fillna(0.0)

    # A settled trade owes nothing either way, so it contributes no exposure.
    live = ~trades["is_settled"]
    trades["exposure_usd"] = trades["mark_usd"].clip(lower=0.0).where(live, 0.0)
    trades["net_usd"] = trades["mark_usd"].where(live, 0.0)
    trades["notional_usd"] = [
        data.fx.to_usd(abs(row.notional), row.currency, as_of) if row.notional and live_row else 0.0
        for row, live_row in zip(trades.itertuples(index=False), live, strict=True)
    ]

    grid = (
        trades.groupby(["counterparty_id", "counterparty_name"])
        .agg(
            open_trades=("is_settled", lambda flags: int((~flags).sum())),
            settled_trades=("is_settled", "sum"),
            books=("book_id", "nunique"),
            gross_notional_usd=("notional_usd", "sum"),
            current_exposure_usd=("exposure_usd", "sum"),
            net_mtm_usd=("net_usd", "sum"),
        )
        .reset_index()
    )

    total = grid["current_exposure_usd"].sum()
    grid["share_of_exposure_pct"] = (
        (grid["current_exposure_usd"] / total * 100).round(2) if total else 0.0
    )

    return grid.sort_values("current_exposure_usd", ascending=False).reset_index(drop=True)
