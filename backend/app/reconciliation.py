"""Blotter against risk file: does the desk's risk describe the desk's book?

Four questions, each of which has a different failure mode:

- does every trade have sensitivities, or is part of the book unmeasured?
- does every sensitivity belong to a trade, or is risk being counted twice?
- does the library's own USD translation agree with the published FX rates?
- is risk still being carried for trades that have already settled?

The last one is the reason this runs as its own report rather than as a footnote
to the risk grid: it is the difference between a risk number a desk can act on
and one that quietly overstates the position.
"""

from datetime import date

import pandas as pd

from app.config import AS_OF_DATE, REPORTING_CCY
from app.dataset import Dataset
from app.issues import DataQualityIssue, IssueCode, Severity, merge
from app.positions import settled_trade_ids

# The published value_usd is rounded to the cent, so the comparison allows a
# cent of slack plus a hair of proportional tolerance for the larger figures.
_ABSOLUTE_TOLERANCE_USD = 0.01
_RELATIVE_TOLERANCE = 1e-6


def _trades_without_risk(data: Dataset, issues: list[DataQualityIssue]) -> None:
    covered = set(data.risk["trade_id"])

    for trade_id in sorted(set(data.trades["trade_id"]) - covered):
        issues.append(
            DataQualityIssue(
                code=IssueCode.TRADE_WITHOUT_RISK,
                severity=Severity.ERROR,
                entity_type="trade",
                entity_id=trade_id,
                detail="the trade is in the blotter but carries no sensitivities",
                treatment=(
                    "Reported: the position is real, so the desk's risk totals "
                    "understate the book until the pricing library covers it."
                ),
            )
        )


def _risk_without_trades(data: Dataset, issues: list[DataQualityIssue]) -> None:
    booked = set(data.trades["trade_id"])

    for trade_id in sorted(set(data.risk["trade_id"]) - booked):
        issues.append(
            DataQualityIssue(
                code=IssueCode.RISK_WITHOUT_TRADE,
                severity=Severity.ERROR,
                entity_type="risk",
                entity_id=trade_id,
                detail="sensitivities are published for a trade that is not in the blotter",
                treatment=(
                    "Excluded from risk totals: risk that maps to no position "
                    "would inflate the book."
                ),
            )
        )


def _value_usd_consistency(data: Dataset, issues: list[DataQualityIssue]) -> None:
    """Check the library's USD figures against the published FX rates.

    Each row is converted at its own as_of_date, not at the date being viewed.
    The risk file is a snapshot: its USD figures were struck on the day it was
    computed, so replaying an earlier day and converting at that day's rate
    compares two different dates and reports every row as broken -- 16 of them
    on this extract, all spurious.

    Restricted to rows denominated in a currency. Duration is quoted in years,
    and converting a tenor through an exchange rate would raise a mismatch on
    every swap in the file for ever -- the kind of permanently red check that
    teaches a desk to ignore the panel.
    """
    convertible = data.risk[(data.risk["unit"] == "amount") & (data.risk["ccy"] != REPORTING_CCY)]

    for row in convertible.itertuples(index=False):
        struck_on = row.as_of_date.date()
        expected = data.fx.to_usd(row.value, row.ccy, struck_on)
        tolerance = max(_ABSOLUTE_TOLERANCE_USD, abs(expected) * _RELATIVE_TOLERANCE)
        if abs(expected - row.value_usd) <= tolerance:
            continue

        issues.append(
            DataQualityIssue(
                code=IssueCode.VALUE_USD_MISMATCH,
                severity=Severity.ERROR,
                entity_type="risk",
                entity_id=f"{row.trade_id}/{row.risk_metric}",
                detail=(
                    f"{row.value:,.2f} {row.ccy} converts to {expected:,.2f} USD at the "
                    f"{struck_on} rate the row was struck on, but the file "
                    f"publishes {row.value_usd:,.2f}"
                ),
                treatment=(
                    "Reported: the two sources disagree on the same figure, so "
                    "neither can be trusted until the difference is explained."
                ),
            )
        )


def _risk_on_settled_trades(data: Dataset, as_of: date, issues: list[DataQualityIssue]) -> None:
    """Sensitivities still published for trades that have already settled.

    Reported per book rather than per trade: what a risk manager needs is the
    size of the overstatement in the number on their screen, not a list.
    """
    settled = settled_trade_ids(data.trades, as_of=as_of)
    if not settled:
        return

    carried = data.risk[data.risk["trade_id"].isin(settled)]
    for (book_id, metric), rows in carried.groupby(["book_id", "risk_metric"]):
        total = rows["value_usd"].sum()
        issues.append(
            DataQualityIssue(
                code=IssueCode.SETTLED_TRADE_CARRIES_RISK,
                severity=Severity.ERROR,
                entity_type="book",
                entity_id=f"{book_id}/{metric}",
                detail=(
                    f"{total:,.2f} USD of {metric} is published for "
                    f"{rows['trade_id'].nunique()} trade(s) that had settled by {as_of}: "
                    f"{', '.join(sorted(rows['trade_id'].unique()))}"
                ),
                treatment=(
                    "Excluded from open risk and reported separately. Including it "
                    "would overstate the book's live exposure by that amount."
                ),
            )
        )


def reconcile(data: Dataset, as_of: date = AS_OF_DATE) -> list[DataQualityIssue]:
    """Run every blotter-against-risk check as one ordered report."""
    issues: list[DataQualityIssue] = []

    _trades_without_risk(data, issues)
    _risk_without_trades(data, issues)
    _value_usd_consistency(data, issues)
    _risk_on_settled_trades(data, as_of, issues)

    return merge(issues)


def coverage_summary(data: Dataset) -> pd.DataFrame:
    """How much of the blotter the risk file actually describes, per book."""
    covered = set(data.risk["trade_id"])
    trades = data.trades.copy()
    trades["has_risk"] = trades["trade_id"].isin(covered)

    return (
        trades.groupby("book_id")
        .agg(trades=("trade_id", "nunique"), with_risk=("has_risk", "sum"))
        .assign(coverage_pct=lambda df: (df["with_risk"] / df["trades"] * 100).round(2))
        .reset_index()
    )
