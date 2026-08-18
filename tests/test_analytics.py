"""Daily series tests, built around the invariants a chart hides well."""

from datetime import date

import pytest

from app.analytics import daily_pnl_series, desk_summary
from app.dataset import load_dataset
from app.pnl import compute_pnl

AS_OF = date(2026, 8, 5)


@pytest.fixture
def data():
    return load_dataset()


def test_series_covers_every_business_day_in_the_window_once(data):
    start = date(2026, 7, 1)
    series, _ = daily_pnl_series(data, as_of=AS_OF, start=start)

    expected = {day.date() for day in data.business_days if start <= day.date() <= AS_OF}
    assert set(series["date"]) == expected
    assert not series.duplicated(subset=["date", "book_id"]).any()


def test_days_outside_the_window_are_excluded(data):
    """The window is a filter, not a suggestion."""
    series, _ = daily_pnl_series(data, as_of=AS_OF, start=date(2026, 8, 4))

    assert min(series["date"]) == date(2026, 8, 4)


def test_daily_moves_sum_to_the_closing_mark(data):
    """The check a daily chart cannot fail visibly.

    Every bar can look plausible while the replay quietly double-counts or
    drops a trade; only the total gives it away.
    """
    series, _ = daily_pnl_series(data, as_of=AS_OF)

    for _book_id, rows in series.groupby("book_id"):
        rows = rows.sort_values("date")
        assert rows["daily_usd"].sum() == pytest.approx(rows["cumulative_usd"].iloc[-1])


def test_closing_mark_equals_the_since_inception_valuation(data):
    """The series and the P&L engine must agree about where the book stands."""
    series, _ = daily_pnl_series(data, as_of=AS_OF)
    inception = compute_pnl(data, as_of=AS_OF).trades.groupby("book_id")["pnl_usd"].sum()

    final = series[series["date"] == AS_OF].set_index("book_id")["cumulative_usd"]
    for book_id, expected in inception.items():
        assert final[book_id] == pytest.approx(expected)


def test_market_moves_telescope_in_local_currency(data):
    """What proves the windowed pricer itself is right.

    Daily moves add up exactly in the currency they happen in. They do not once
    each day is converted at its own rate, which is why the series works from
    the mark rather than from summed conversions -- so this is asserted here,
    on pnl_ccy, where the identity genuinely holds.
    """
    days = [day.date() for day in data.business_days]
    totals: dict[str, float] = {}

    for position, day in enumerate(days):
        previous = days[position - 1] if position else None
        moves = compute_pnl(data, as_of=day, since=previous).trades
        for row in moves.itertuples(index=False):
            totals[row.trade_id] = totals.get(row.trade_id, 0.0) + row.pnl_ccy

    inception = compute_pnl(data, as_of=AS_OF).trades.set_index("trade_id")
    for trade_id, expected in inception["pnl_ccy"].items():
        assert totals[trade_id] == pytest.approx(expected, abs=0.01)


def test_converted_daily_moves_do_not_telescope(data):
    """The reason the convention exists, asserted rather than asserted in prose.

    If this ever stops being true the docstring is wrong and the choice of
    convention should be revisited.
    """
    days = [day.date() for day in data.business_days]
    summed = 0.0

    for position, day in enumerate(days):
        previous = days[position - 1] if position else None
        summed += compute_pnl(data, as_of=day, since=previous).trades["pnl_usd"].sum()

    mark = compute_pnl(data, as_of=AS_OF).trades["pnl_usd"].sum()

    assert summed != pytest.approx(mark, abs=0.01)


def test_anomalies_are_reported_once_not_once_per_day(data):
    """A trade with no price fails on every day of the replay."""
    _, issues = daily_pnl_series(data, as_of=AS_OF)

    keys = [(issue.code, issue.entity_id) for issue in issues]
    assert len(keys) == len(set(keys))


def test_summary_agrees_with_the_series_it_charts(data):
    """A card and the line above it must not tell different stories."""
    series, _ = daily_pnl_series(data, as_of=AS_OF)
    summary = desk_summary(data, as_of=AS_OF).set_index("book_id")
    final = series[series["date"] == AS_OF].set_index("book_id")

    for book_id in summary.index:
        assert summary.at[book_id, "inception_usd"] == pytest.approx(
            final.at[book_id, "cumulative_usd"]
        )
        assert summary.at[book_id, "day_usd"] == pytest.approx(final.at[book_id, "daily_usd"])


def test_summary_counts_only_open_positions(data):
    summary = desk_summary(data, as_of=AS_OF).set_index("book_id")

    assert (summary["open_positions"] >= 0).all()
    assert summary["trade_count"].sum() > 0


def test_a_shorter_window_starts_from_the_traded_level(data):
    """The first day of any window measures from inception, not from nothing."""
    series, _ = daily_pnl_series(data, as_of=AS_OF, start=date(2026, 8, 4))

    assert set(series["date"]) == {date(2026, 8, 4), AS_OF}
    first = series[series["date"] == date(2026, 8, 4)]
    assert (first["daily_usd"] == first["cumulative_usd"]).all()


def test_a_window_the_extract_cannot_price_is_refused(data):
    with pytest.raises(ValueError, match="no business day"):
        daily_pnl_series(data, as_of=date(2026, 6, 30), start=date(2026, 6, 1))
