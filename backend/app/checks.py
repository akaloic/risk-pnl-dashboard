"""Quality checks on the market data and the risk file.

Blotter defects are handled where the blotter is cleaned; these are the checks
that need a quote or a sensitivity to make sense. They only ever report -- none
of them changes a number -- because the treatment for a stale price or an
impossible duration is to make sure nobody prices off it, and that decision
belongs to the desk rather than to a loader.
"""

import pandas as pd

from app.config import AS_OF_DATE
from app.dataset import Dataset
from app.issues import DataQualityIssue, IssueCode, Severity, merge

DAYS_PER_YEAR = 365.25

# A modified duration below this share of the remaining tenor is not credible
# for a par swap or a coupon bond. Set well below any real figure -- the four
# swaps here come in at 0.09 and 0.18 -- so that it flags fabricated values
# rather than merely short ones.
_MIN_CREDIBLE_DURATION_RATIO = 0.25


def _stale_quotes(data: Dataset, issues: list[DataQualityIssue]) -> None:
    """Quotes whose timestamp belongs to a different day than their snapshot.

    A snapshot dated today carrying yesterday's timestamp is yesterday's price
    wearing today's date: it will not move when the market does, and the P&L it
    produces looks perfectly normal.
    """
    quotes = data.quotes
    quote_day = quotes["last_update_utc"].dt.tz_convert(None).dt.normalize()
    stale = quote_day != quotes["date"]

    for row in quotes[stale].itertuples(index=False):
        issues.append(
            DataQualityIssue(
                code=IssueCode.STALE_QUOTE,
                severity=Severity.WARNING,
                entity_type="quote",
                entity_id=f"{row.instrument_id}@{row.date.date()}",
                detail=(
                    f"snapshot dated {row.date.date()} carries a quote timestamped "
                    f"{row.last_update_utc.date()}: the price is a day old"
                ),
                treatment=(
                    "Used as published, since it is the only price for that day, "
                    "and reported so the P&L it feeds can be challenged."
                ),
            )
        )


def _implausible_durations(
    data: Dataset, as_of: pd.Timestamp, issues: list[DataQualityIssue]
) -> None:
    """Durations that cannot be right, by two different tests.

    A modified duration cannot exceed the time left to maturity: a bond
    maturing in ten months cannot have eight years of duration. And a duration
    that is a small fraction of the tenor, identical across a five-year and a
    ten-year swap, is a placeholder rather than a measurement.
    """
    durations = data.risk[data.risk["risk_metric"] == "Duration"]
    maturities = data.trades.set_index("trade_id")["maturity_date"]

    for row in durations.itertuples(index=False):
        maturity = maturities.get(row.trade_id)
        if maturity is None or pd.isna(maturity):
            continue

        years_left = (maturity - as_of).days / DAYS_PER_YEAR
        if years_left <= 0:
            continue

        if row.value <= 0:
            reason = f"duration {row.value} is not positive"
        elif row.value > years_left:
            reason = (
                f"duration {row.value:.4f}y exceeds the {years_left:.2f}y left to "
                "maturity, which no modified duration can do"
            )
        elif row.value / years_left < _MIN_CREDIBLE_DURATION_RATIO:
            reason = (
                f"duration {row.value:.4f}y is only {row.value / years_left:.0%} of the "
                f"{years_left:.2f}y tenor, too low to be a real measurement"
            )
        else:
            continue

        issues.append(
            DataQualityIssue(
                code=IssueCode.IMPLAUSIBLE_DURATION,
                severity=Severity.WARNING,
                entity_type="trade",
                entity_id=str(row.trade_id),
                detail=reason,
                treatment=(
                    "Reported only. Duration feeds no P&L or risk total here, so "
                    "the figure is quarantined rather than used."
                ),
            )
        )


def _orphan_quotes(data: Dataset, issues: list[DataQualityIssue]) -> None:
    """Instruments quoted every day that the desk holds no position in.

    Harmless -- the position is simply zero -- but worth stating, so that the
    next person to compare the two files does not go looking for missing
    trades.
    """
    held = set(data.trades["instrument_id"])
    for instrument in sorted(set(data.quotes["instrument_id"]) - held):
        issues.append(
            DataQualityIssue(
                code=IssueCode.QUOTE_WITHOUT_POSITION,
                severity=Severity.INFO,
                entity_type="instrument",
                entity_id=instrument,
                detail="quoted in the market data but not held in any book",
                treatment="Ignored: the position is zero, so there is nothing to value.",
            )
        )


def _price_yield_incoherence(data: Dataset, issues: list[DataQualityIssue]) -> None:
    """Bond price and yield columns that do not move against each other.

    Price and yield are two views of the same thing, so a price rising while
    the yield rises too is a contradiction. Implying a negative duration is the
    clearest way to show it: the two columns were not derived from one another,
    which is why bonds here are valued on price alone and never cross-checked
    against the yield series.
    """
    bonds = data.quotes[data.quotes["price_type"] == "CLEAN"]

    for instrument, series in bonds.groupby("instrument_id"):
        series = series.sort_values("date")
        price_move = series["px_mid"].diff()
        yield_move = series["yield_pct"].diff()

        moved = yield_move.abs() > 1e-9
        if not moved.any():
            continue

        implied = (-price_move / series["px_mid"] * 100 / yield_move)[moved]
        if implied.median() >= 0:
            continue

        issues.append(
            DataQualityIssue(
                code=IssueCode.PRICE_YIELD_INCOHERENT,
                severity=Severity.WARNING,
                entity_type="instrument",
                entity_id=str(instrument),
                detail=(
                    f"price and yield moves imply a median duration of "
                    f"{implied.median():.2f} years, which is negative: the two columns "
                    "are not consistent with each other"
                ),
                treatment=(
                    "Bonds are valued on the clean price, per the desk's method. "
                    "The yield column is not used to derive or verify P&L."
                ),
            )
        )


def run_checks(data: Dataset, as_of=AS_OF_DATE) -> list[DataQualityIssue]:
    """Every market data and risk file check, as one ordered report."""
    issues: list[DataQualityIssue] = []
    as_of_ts = pd.Timestamp(as_of)

    _stale_quotes(data, issues)
    _implausible_durations(data, as_of_ts, issues)
    _orphan_quotes(data, issues)
    _price_yield_incoherence(data, issues)

    return merge(issues)
