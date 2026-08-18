"""Net positions by book and instrument, as of a given date.

Two judgements drive this module, and both are easy to get quietly wrong.

*What counts as still open.* Settlement closes a trade only for products whose
economics end at settlement. An FX spot that has settled is finished: the cash
was exchanged and nothing remains to mark. A settled *bond purchase* is the
opposite -- settlement is the moment the bonds were delivered, so the position
only then becomes real. The same is true of a swap past its effective date. In
this blotter 34 of 40 trades have a settlement date in the past, so a rule
keyed on settle_date alone would empty the book.

*Which date closes an FX trade.* For spot it is settle_date. For forwards and
NDFs it is maturity_date: the NDFs here carry settle_date = trade date + 2
business days, the spot-leg convention, while the contract actually runs to
maturity a month later. Closing them on settle_date would retire two live
positions and discard their delta.
"""

from datetime import date
from enum import Enum
from typing import NamedTuple

import pandas as pd
from pydantic import BaseModel

from app.config import AS_OF_DATE
from app.issues import DataQualityIssue, IssueCode, Severity, merge
from app.models import AssetClass, ProductType

# Products whose economics end at settlement, with the field that closes them.
# Anything absent from this mapping stays open regardless of its settlement
# date -- that is what protects the bond and swap book.
_CLOSING_DATE_FIELD = {
    ProductType.FX_SPOT.value: "settle_date",
    ProductType.FX_FORWARD.value: "maturity_date",
    ProductType.FX_NDF.value: "maturity_date",
}

# Identity of a position. instrument_description is deliberately absent: the
# blotter describes the same contract differently on different rows ("Nikkei
# 225 Future Sep26" vs "... Sep26 short"), and grouping on it would split one
# net future into two half-positions.
_POSITION_KEY = [
    "book_id",
    "asset_class",
    "product_type",
    "instrument_id",
    "currency",
    "maturity_date",
    "position_status",
]


class PositionStatus(str, Enum):
    OPEN = "OPEN"
    SETTLED = "SETTLED"


class Position(BaseModel):
    """A netted position.

    net_quantity and net_notional are both signed by direction, and which one
    carries meaning depends on the product: equity options and futures book a
    notional of zero, so quantity is their measure, while swaps and FX carry a
    quantity of 1 per trade and are only meaningful in notional. Bond quantity
    is not comparable across markets either -- the blotter's notional-to-
    quantity ratio is 100, 1,000 or 100,000 depending on the currency -- which
    is why bonds are valued on face amount rather than on quantity.
    """

    book_id: str
    asset_class: AssetClass
    product_type: ProductType
    instrument_id: str
    instrument_description: str
    currency: str
    position_status: PositionStatus
    maturity_date: date | None = None
    net_quantity: float
    gross_quantity: float
    net_notional: float
    trade_count: int
    trade_ids: list[str]


class PositionBook(NamedTuple):
    positions: pd.DataFrame
    issues: list[DataQualityIssue]


def closing_dates(trades: pd.DataFrame) -> pd.Series:
    """The date each trade ceases to be a position, NaT if settlement never closes it."""
    closing = pd.Series(pd.NaT, index=trades.index, dtype="datetime64[ns]")
    for product_type, field in _CLOSING_DATE_FIELD.items():
        rows = trades["product_type"] == product_type
        closing[rows] = trades.loc[rows, field]
    return closing


def _flag_settled_but_live(
    trades: pd.DataFrame,
    settled: pd.Series,
    closed_on: pd.Series,
    issues: list[DataQualityIssue],
) -> None:
    """Report trades the blotter still calls LIVE after they have closed.

    Reads the date from `closed_on` rather than from settle_date: a forward or
    NDF closes on maturity, so quoting its settle_date here would report the
    wrong date -- and a blank one would not print at all.
    """
    contradictory = settled & (trades["status"].str.upper() == "LIVE")

    for idx in trades.index[contradictory]:
        closing = closed_on[idx]
        issues.append(
            DataQualityIssue(
                code=IssueCode.SETTLED_TRADE_MARKED_LIVE,
                severity=Severity.WARNING,
                entity_type="trade",
                entity_id=str(trades.at[idx, "trade_id"]),
                detail=(
                    f"blotter status is LIVE but the trade settled on "
                    f"{closing.date()}, before the as-of date"
                ),
                treatment=(
                    "Classified SETTLED and reported separately from open risk. "
                    "The status column is not trusted over the settlement date."
                ),
            )
        )


def _flag_unknown_settlement(
    trades: pd.DataFrame, as_of: pd.Timestamp, issues: list[DataQualityIssue]
) -> None:
    """Report FX spot with no settle_date whose maturity has nonetheless passed.

    Left open rather than assumed settled: the documented rule keys on
    settle_date, and overriding it on inference would silently retire a
    position. Raised as an ERROR because the evidence points the other way and
    a human should decide -- carrying it open overstates the desk's open FX
    delta, while retiring it wrongly would understate it.
    """
    spot = trades["product_type"] == ProductType.FX_SPOT.value
    unknown = spot & trades["settle_date"].isna() & trades["maturity_date"].notna()
    unknown &= trades["maturity_date"] < as_of

    for idx in trades.index[unknown]:
        maturity = trades.at[idx, "maturity_date"].date()
        issues.append(
            DataQualityIssue(
                code=IssueCode.SETTLEMENT_STATE_UNKNOWN,
                severity=Severity.ERROR,
                entity_type="trade",
                entity_id=str(trades.at[idx, "trade_id"]),
                detail=(
                    f"FX spot has no settle_date, but its maturity {maturity} has "
                    f"passed as of {as_of.date()}: it has probably settled"
                ),
                treatment=(
                    "Kept OPEN, since settlement cannot be confirmed from the "
                    "extract. Confirm with operations before trusting the FX delta."
                ),
            )
        )


def _flag_term_fx_settle_convention(
    trades: pd.DataFrame, issues: list[DataQualityIssue]
) -> None:
    """Report term FX whose settle_date precedes its maturity.

    On those rows settle_date is the spot leg (trade date + 2 business days),
    not the settlement of the contract. Recording it means the next person to
    read this file does not have to rediscover why settle_date is ignored for
    forwards and NDFs.
    """
    term = trades["product_type"].isin([ProductType.FX_FORWARD.value, ProductType.FX_NDF.value])
    mismatched = (
        term
        & trades["settle_date"].notna()
        & trades["maturity_date"].notna()
        & (trades["settle_date"] < trades["maturity_date"])
    )

    for idx in trades.index[mismatched]:
        settle = trades.at[idx, "settle_date"].date()
        maturity = trades.at[idx, "maturity_date"].date()
        issues.append(
            DataQualityIssue(
                code=IssueCode.TERM_FX_SETTLE_BEFORE_MATURITY,
                severity=Severity.WARNING,
                entity_type="trade",
                entity_id=str(trades.at[idx, "trade_id"]),
                detail=(
                    f"settle_date {settle} precedes maturity {maturity}: settle_date "
                    "carries the spot leg, not the settlement of the contract"
                ),
                treatment=(
                    "Position closed on maturity_date instead. Using settle_date "
                    "would retire the contract a month early and drop its delta."
                ),
            )
        )


def build_positions(trades: pd.DataFrame, as_of: date = AS_OF_DATE) -> PositionBook:
    """Net a cleaned blotter into positions as of `as_of`.

    Expects the output of dq.clean_trades: quantity as a magnitude, with
    direction_sign carrying the side. Trades booked after `as_of` are excluded
    so the same function can replay any business day; a trade whose date could
    not be repaired compares false here and is left out, having already been
    raised as an error by the cleaning step.
    """
    as_of_ts = pd.Timestamp(as_of)
    issues: list[DataQualityIssue] = []

    df = trades[trades["trade_date"].notna() & (trades["trade_date"] <= as_of_ts)].copy()

    closing = closing_dates(df)
    settled = closing.notna() & (closing < as_of_ts)

    _flag_settled_but_live(df, settled, closing, issues)
    _flag_unknown_settlement(df, as_of_ts, issues)
    _flag_term_fx_settle_convention(df, issues)

    # Deliberately a new column rather than an overwrite of `status`: that one
    # carries what the blotter claims, which the checks above compare against
    # and which stays available for reconciliation.
    df["position_status"] = pd.Series(
        [PositionStatus.SETTLED.value if flag else PositionStatus.OPEN.value for flag in settled],
        index=df.index,
    )
    df["signed_quantity"] = df["quantity"] * df["direction_sign"]
    df["signed_notional"] = df["notional"] * df["direction_sign"]

    grouped = (
        df.groupby(_POSITION_KEY, dropna=False, observed=True)
        .agg(
            instrument_description=("instrument_description", "first"),
            net_quantity=("signed_quantity", "sum"),
            gross_quantity=("quantity", "sum"),
            net_notional=("signed_notional", "sum"),
            trade_count=("trade_id", "size"),
            trade_ids=("trade_id", lambda ids: sorted(ids)),
        )
        .reset_index()
        .sort_values(["book_id", "instrument_id", "product_type"])
        .reset_index(drop=True)
    )

    return PositionBook(positions=grouped, issues=merge(issues))
