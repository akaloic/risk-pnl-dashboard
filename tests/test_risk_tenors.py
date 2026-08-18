"""The curve split: where a book's risk sits, not just how much of it there is."""

from datetime import date

import pandas as pd
import pytest

from app.dataset import load_dataset
from app.risk import aggregate_risk, risk_by_tenor, tenor_bucket

AS_OF = date(2026, 8, 5)


@pytest.fixture
def data():
    # Function-scoped on purpose. The autouse fixture in conftest that redirects
    # RAD_DATA_DIR at tests/fixtures/ is function-scoped too, and a module-scoped
    # dataset here would be built before it runs -- reaching for the real
    # extracts and failing on a fresh clone that has none.
    return load_dataset()


@pytest.mark.parametrize(
    ("maturity", "expected"),
    [
        ("2026-08-04", "Matured"),
        ("2026-08-05", "Matured"),
        ("2026-09-01", "0-1Y"),
        ("2027-08-05", "0-1Y"),
        ("2027-08-06", "1-3Y"),
        ("2029-08-05", "1-3Y"),
        ("2029-08-06", "3-5Y"),
        ("2031-08-05", "3-5Y"),
        ("2031-08-06", "5-10Y"),
        ("2036-08-05", "5-10Y"),
        ("2036-08-06", "10Y+"),
        ("2043-01-01", "10Y+"),
    ],
)
def test_a_maturity_lands_in_the_bucket_that_ends_on_it(maturity, expected):
    """The upper bound is inclusive: a trade maturing on its own anniversary
    belongs to the bucket that anniversary names, and the day after does not.

    Every pair here straddles a boundary. 2036-08-05 is the one that a day
    count gets wrong: it is ten calendar years out but 3,653 days, which over
    365.25 reads as 10.0014 and would drop a plain 10Y swap into 10Y+.
    """
    assert tenor_bucket(pd.Timestamp(maturity), AS_OF) == expected


def test_a_trade_already_past_maturity_is_not_folded_into_the_front_bucket():
    """Matured is its own bucket because a figure there is a finding.

    Dropping it into 0-1Y would present exposure that has expired as the
    nearest live point on the curve.
    """
    assert tenor_bucket(pd.Timestamp("2026-07-29"), AS_OF) == "Matured"
    assert tenor_bucket(pd.NaT, AS_OF) == "Matured"


def test_the_split_adds_back_to_the_book_grid(data):
    """Every dollar of open risk lands in exactly one bucket, and none is lost."""
    by_tenor = risk_by_tenor(data, as_of=AS_OF)
    by_book = aggregate_risk(data, as_of=AS_OF)

    split = by_tenor.groupby(["book_id", "risk_metric"])["open_usd"].sum()
    grid = by_book.set_index(["book_id", "risk_metric"])["open_usd"]

    assert not split.empty
    for key, total in split.items():
        assert total == pytest.approx(grid[key], abs=0.01)


def test_buckets_come_back_in_curve_order_not_alphabetical(data):
    """Sorted as text, 10Y+ falls between 0-1Y and 1-3Y and the curve reads wrong."""
    order = ["Matured", "0-1Y", "1-3Y", "3-5Y", "5-10Y", "10Y+"]
    by_tenor = risk_by_tenor(data, as_of=AS_OF)

    for _, rows in by_tenor.groupby(["book_id", "risk_metric"], sort=False):
        positions = [order.index(bucket) for bucket in rows["tenor_bucket"]]
        assert positions == sorted(positions)


def test_settled_risk_is_absent_from_the_curve(data):
    """Settled exposure is a data quality finding, not a point on the curve.

    FIX-008 is an FX spot that settled on 2026-07-29 and whose delta the risk
    file still publishes. It stays visible in the book grid's settled column;
    asking where on the curve it sits has no answer.
    """
    by_tenor = risk_by_tenor(data, as_of=AS_OF)
    by_book = aggregate_risk(data, as_of=AS_OF)

    assert by_book["settled_usd"].abs().sum() > 0
    assert by_tenor["open_usd"].sum() == pytest.approx(by_book["open_usd"].sum(), abs=0.01)


def test_duration_is_excluded_because_it_cannot_be_added(data):
    """Same rule as the book grid: years do not sum, in a bucket or out of one."""
    assert "Duration" not in set(risk_by_tenor(data, as_of=AS_OF)["risk_metric"])


def test_one_metric_spreads_across_the_buckets_its_trades_mature_in(data):
    """The reason the view exists: a single total covers several points.

    Delta_USD in the fixtures spans a matured spot and a run of trades inside
    the year, and the book grid reports the two as one number.
    """
    delta = risk_by_tenor(data, as_of=AS_OF)
    delta = delta[delta["risk_metric"] == "Delta_USD"]

    assert len(delta) > 1
    assert set(delta["tenor_bucket"]) == {"Matured", "0-1Y"}


def test_an_unconfirmed_settlement_surfaces_as_matured_risk(data):
    """FIX-007 mirrors TRD-027: maturity passed, settle_date blank.

    The documented rule keys on settle_date and cannot retire it, so it is
    deliberately left open -- and open risk on a matured trade is precisely
    what the Matured bucket exists to make visible rather than round away.
    """
    by_tenor = risk_by_tenor(data, as_of=AS_OF)
    matured = by_tenor[by_tenor["tenor_bucket"] == "Matured"]

    assert list(matured["risk_metric"]) == ["Delta_USD"]
    assert matured["open_usd"].sum() == pytest.approx(3_000_000.0, abs=1.0)
