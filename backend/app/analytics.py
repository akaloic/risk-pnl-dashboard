"""The desk view: P&L replayed day by day, and summarised per book.

The series marks the whole book on each business day the extract publishes,
and takes each day's move as the change in that mark. Doing it in that order,
rather than summing independently computed daily moves, is a deliberate choice
about a multi-currency book.

Market moves telescope in the currency they happen in: a JPY bond's price moves
sum to its total move. They do *not* telescope once each day is converted at
its own rate, because sum(dL_k / fx_k) is not (L_n - L_0) / fx_n. On this
extract the two differ by around 2,200 USD on the equity book alone. Neither
figure is wrong; they answer different questions. Summing daily conversions
gives the trading move excluding any revaluation of prior P&L, while the change
in the mark is what a USD-reporting desk actually has, because yesterday's yen
profit is worth a different number of dollars today.

The mark is the figure a desk is accountable for, so the mark is what this
reports -- and defining the daily move as its change guarantees that the chart
and the summary card can never disagree. The pricing engine's own windowed mode
is verified separately, in local currency, where the telescoping does hold
exactly: that is what proves the replay is not dropping or double-counting
trades, a failure a daily chart hides well because every individual bar still
looks plausible.
"""

from datetime import date

import pandas as pd
from pydantic import BaseModel

from app.config import AS_OF_DATE, HISTORY_START_DATE
from app.dataset import Dataset
from app.issues import DataQualityIssue, merge
from app.pnl import compute_pnl
from app.positions import PositionStatus, build_positions


class DailyPnL(BaseModel):
    """One business day of P&L for one book."""

    date: date
    book_id: str
    daily_usd: float
    cumulative_usd: float


class BookSummary(BaseModel):
    """The figures behind a desk summary card."""

    book_id: str
    day_usd: float
    inception_usd: float
    trade_count: int
    open_positions: int


def _window(data: Dataset, start: date, end: date) -> list[pd.Timestamp]:
    days = [day for day in data.business_days if pd.Timestamp(start) <= day <= pd.Timestamp(end)]
    if not days:
        raise ValueError(
            f"the extract prices no business day between {start} and {end}; "
            f"it covers {data.business_days[0].date()} to {data.business_days[-1].date()}"
        )
    return days


def daily_pnl_series(
    data: Dataset,
    as_of: date = AS_OF_DATE,
    start: date = HISTORY_START_DATE,
) -> tuple[pd.DataFrame, list[DataQualityIssue]]:
    """P&L per book for every business day in the window, plus the running total.

    Issues raised while valuing are deduplicated across days: a trade with no
    price fails on all twenty-four of them, and reporting that twenty-four
    times would bury every other finding in the report.
    """
    days = _window(data, start, as_of)
    marks: list[dict] = []
    seen: dict[tuple, DataQualityIssue] = {}

    for day in days:
        valued = compute_pnl(data, as_of=day.date())

        for issue in valued.issues:
            seen.setdefault((issue.code, issue.entity_id), issue)

        for book_id, amount in valued.trades.groupby("book_id")["pnl_usd"].sum().items():
            marks.append(
                {"date": day.date(), "book_id": book_id, "cumulative_usd": float(amount)}
            )

    series = pd.DataFrame(marks, columns=["date", "book_id", "cumulative_usd"])
    if series.empty:
        series["daily_usd"] = pd.Series(dtype=float)
        return series[["date", "book_id", "daily_usd", "cumulative_usd"]], merge(
            list(seen.values())
        )

    # A book with no trades yet is absent from the early days rather than
    # present at zero, so fill the grid before differencing: otherwise its
    # first appearance would be read as a jump from nothing.
    grid = (
        series.pivot(index="date", columns="book_id", values="cumulative_usd")
        .reindex([day.date() for day in days])
        .fillna(0.0)
        .sort_index()
    )

    daily = grid.diff()
    daily.iloc[0] = grid.iloc[0]

    return (
        grid.stack()
        .rename("cumulative_usd")
        .reset_index()
        .merge(
            daily.stack().rename("daily_usd").reset_index(),
            on=["date", "book_id"],
        )[["date", "book_id", "daily_usd", "cumulative_usd"]]
        .sort_values(["book_id", "date"])
        .reset_index(drop=True),
        merge(list(seen.values())),
    )


def desk_summary(data: Dataset, as_of: date = AS_OF_DATE) -> pd.DataFrame:
    """One row per book: today's move, the position since inception, and size.

    Both P&L figures are read off the same series that feeds the chart, so a
    card and the line above it cannot tell different stories.
    """
    series, _ = daily_pnl_series(data, as_of=as_of)
    latest = series[series["date"] == as_of].set_index("book_id")

    inception = compute_pnl(data, as_of=as_of).trades
    book = build_positions(data.trades, as_of=as_of)
    positions = book.positions
    open_counts = (
        positions[positions["position_status"] == PositionStatus.OPEN.value]
        .groupby("book_id")
        .size()
    )

    summary = (
        inception.groupby("book_id")
        .agg(trade_count=("trade_id", "nunique"))
        .join(latest["daily_usd"].rename("day_usd"))
        .join(latest["cumulative_usd"].rename("inception_usd"))
        .join(open_counts.rename("open_positions"))
        .fillna({"day_usd": 0.0, "inception_usd": 0.0, "open_positions": 0})
        .reset_index()
    )
    summary["open_positions"] = summary["open_positions"].astype(int)

    return summary[
        ["book_id", "day_usd", "inception_usd", "trade_count", "open_positions"]
    ].sort_values("book_id").reset_index(drop=True)
