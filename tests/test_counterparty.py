"""Counterparty exposure: what a default would cost, not how big the relationship is."""

from datetime import date

import pytest

from app.counterparty import exposure_by_counterparty
from app.dataset import load_dataset
from app.pnl import compute_pnl
from app.positions import settled_trade_ids

AS_OF = date(2026, 8, 5)


@pytest.fixture
def data():
    return load_dataset()


def by_id(grid):
    return grid.set_index("counterparty_id")


def test_exposure_counts_only_what_the_counterparty_owes(data):
    """Credit exposure is the mark where it is positive and zero where it is not.

    A trade marked against the desk costs nothing if the counterparty defaults --
    the desk is the one who owes. Netting the two would report a relationship as
    safe because the desk happens to be losing on it.
    """
    grid = exposure_by_counterparty(data, as_of=AS_OF)

    assert (grid["current_exposure_usd"] >= 0).all()
    assert (grid["current_exposure_usd"] >= grid["net_mtm_usd"]).all()


def test_a_relationship_losing_money_can_still_be_owed_money(data):
    """The distinction the view exists to make.

    CPTY-T3 nets to -23,112: on the whole relationship the desk is down. Netting
    would report it as costing nothing to lose, when one of its trades is marked
    4,000 in the desk's favour and that is precisely what a default takes away.
    """
    grid = by_id(exposure_by_counterparty(data, as_of=AS_OF))
    losing = grid[grid["net_mtm_usd"] < 0]

    assert not losing.empty
    assert (losing["current_exposure_usd"] > 0).any()


def test_notional_is_converted_before_it_is_compared(data):
    """Summed raw, the column mixes JPY, KRW and USD and ranks by unit size.

    The check that catches it: no counterparty's USD notional may exceed the
    sum of the raw figures, which it would the moment a JPY notional were added
    to a USD one without conversion.
    """
    grid = exposure_by_counterparty(data, as_of=AS_OF)
    raw_total = data.trades["notional"].abs().sum()

    assert grid["gross_notional_usd"].sum() < raw_total


def test_settled_trades_owe_nothing_either_way(data):
    """The cash was exchanged, so there is no one left to default.

    They stay in the settled column, because the size of a relationship is a
    fact about the desk even once its trades have closed.
    """
    grid = exposure_by_counterparty(data, as_of=AS_OF)
    settled = settled_trade_ids(data.trades, as_of=AS_OF)

    assert grid["settled_trades"].sum() == len(settled)
    only_settled = grid[grid["open_trades"] == 0]
    assert (only_settled["current_exposure_usd"] == 0).all()


def test_every_trade_is_attributed_to_exactly_one_counterparty(data):
    """A trade counted twice inflates a limit; one dropped hides a breach."""
    grid = exposure_by_counterparty(data, as_of=AS_OF)

    assert grid["open_trades"].sum() + grid["settled_trades"].sum() == len(data.trades)


def test_the_exposure_total_matches_the_positive_marks(data):
    """Tie-out against the pricing engine rather than against itself."""
    priced, _ = compute_pnl(data, as_of=AS_OF)
    settled = settled_trade_ids(data.trades, as_of=AS_OF)
    live = priced[~priced["trade_id"].isin(settled)]
    expected = live["pnl_usd"].clip(lower=0).sum()

    grid = exposure_by_counterparty(data, as_of=AS_OF)

    assert grid["current_exposure_usd"].sum() == pytest.approx(expected, abs=0.01)


def test_shares_are_a_percentage_of_the_desk(data):
    grid = exposure_by_counterparty(data, as_of=AS_OF)

    assert grid["share_of_exposure_pct"].sum() == pytest.approx(100.0, abs=0.05)


def test_the_ranking_is_by_exposure_not_by_size(data):
    """Sorted by notional this list is a different list, which is the point."""
    grid = exposure_by_counterparty(data, as_of=AS_OF)

    assert list(grid["current_exposure_usd"]) == sorted(grid["current_exposure_usd"], reverse=True)
    assert list(grid["counterparty_id"]) != list(
        grid.sort_values("gross_notional_usd", ascending=False)["counterparty_id"]
    )


def test_a_trade_the_engine_could_not_mark_adds_no_exposure(data):
    """A trade excluded from P&L contributes nothing, and still counts as one.

    The engine refuses to value a trade it has no price for, so its mark is
    absent rather than zero. Treating the absence as zero exposure is right --
    nothing is known to be owed; dropping the trade from the count would
    understate how much business the desk does with that name.

    The fixtures price every trade, so this pins the arithmetic rather than the
    path: exposure comes from the marks that exist, the counts from every row.
    """
    priced, _ = compute_pnl(data, as_of=AS_OF)
    grid = exposure_by_counterparty(data, as_of=AS_OF)

    assert grid["current_exposure_usd"].sum() == pytest.approx(
        priced.loc[~priced["trade_id"].isin(settled_trade_ids(data.trades, as_of=AS_OF)), "pnl_usd"]
        .clip(lower=0)
        .sum(),
        abs=0.01,
    )
    assert grid["open_trades"].sum() + grid["settled_trades"].sum() == len(data.trades)
