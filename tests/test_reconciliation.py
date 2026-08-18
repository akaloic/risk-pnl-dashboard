"""Blotter against risk file, and the risk grid built on top of it."""

from dataclasses import replace
from datetime import date

import pandas as pd
import pytest

from app.dataset import load_dataset
from app.issues import IssueCode, Severity
from app.reconciliation import coverage_summary, reconcile
from app.risk import aggregate_risk, non_additive_metrics

AS_OF = date(2026, 8, 5)


@pytest.fixture
def data():
    return load_dataset()


def _issues_for(issues, code):
    return [issue for issue in issues if issue.code == code]


# --- reconciliation ----------------------------------------------------------


def test_a_trade_with_no_sensitivities_is_flagged(data):
    """Part of the book would otherwise go unmeasured without anyone noticing."""
    risk = data.risk[data.risk["trade_id"] != "FIX-004"]

    found = _issues_for(reconcile(_with(data, risk=risk), AS_OF), IssueCode.TRADE_WITHOUT_RISK)

    assert [issue.entity_id for issue in found] == ["FIX-004"]
    assert found[0].severity == Severity.ERROR


def test_risk_for_a_trade_that_is_not_booked_is_flagged(data):
    """Risk mapping to no position inflates the book."""
    orphan = data.risk.iloc[[0]].assign(trade_id="FIX-999")
    risk = pd.concat([data.risk, orphan], ignore_index=True)

    found = _issues_for(reconcile(_with(data, risk=risk), AS_OF), IssueCode.RISK_WITHOUT_TRADE)

    assert [issue.entity_id for issue in found] == ["FIX-999"]


def test_the_fixture_reconciles_both_ways(data):
    issues = reconcile(data, AS_OF)

    assert _issues_for(issues, IssueCode.TRADE_WITHOUT_RISK) == []
    assert _issues_for(issues, IssueCode.RISK_WITHOUT_TRADE) == []


def test_published_usd_values_are_checked_against_the_rate_grid(data):
    """FIX-001's DV01 of 100,000 JPY must be 666.67 USD at 150.00."""
    assert _issues_for(reconcile(data, AS_OF), IssueCode.VALUE_USD_MISMATCH) == []

    risk = data.risk.copy()
    row = (risk["trade_id"] == "FIX-001") & (risk["risk_metric"] == "DV01")
    risk.loc[row, "value_usd"] = 700.00

    found = _issues_for(reconcile(_with(data, risk=risk), AS_OF), IssueCode.VALUE_USD_MISMATCH)
    assert [issue.entity_id for issue in found] == ["FIX-001/DV01"]


def test_usd_values_are_checked_at_the_date_they_were_struck(data):
    """Replaying an earlier day must not report the whole risk file as broken.

    The risk file is a snapshot: its USD figures were converted on the day it
    was computed. Converting them at the date being *viewed* compares two
    different days and flags every foreign-currency row -- 16 spurious breaks
    on the real extract.
    """
    on_the_day = reconcile(data, AS_OF)
    replayed = reconcile(data, date(2026, 7, 2))

    assert _issues_for(on_the_day, IssueCode.VALUE_USD_MISMATCH) == []
    assert _issues_for(replayed, IssueCode.VALUE_USD_MISMATCH) == []


def test_durations_are_not_run_through_the_rate_check(data):
    """Converting a tenor would fail on every swap in the file, permanently.

    A check that is always red is a check a desk learns to ignore, so the
    comparison is restricted to rows denominated in a currency.
    """
    risk = data.risk.copy()
    row = (risk["trade_id"] == "FIX-001") & (risk["risk_metric"] == "Duration")
    risk.loc[row, "ccy"] = "JPY"

    found = _issues_for(reconcile(_with(data, risk=risk), AS_OF), IssueCode.VALUE_USD_MISMATCH)

    assert [issue.entity_id for issue in found] == []


def test_risk_still_carried_for_a_settled_trade_is_flagged(data):
    """FIX-008 settled on 2026-07-29 and the file still publishes its delta."""
    found = _issues_for(reconcile(data, AS_OF), IssueCode.SETTLED_TRADE_CARRIES_RISK)

    assert len(found) == 1
    assert "FIX-008" in found[0].detail
    assert found[0].severity == Severity.ERROR
    assert "overstate" in found[0].treatment


def test_coverage_summary_reports_every_book(data):
    coverage = coverage_summary(data)

    assert set(coverage["book_id"]) == set(data.trades["book_id"])
    assert (coverage["coverage_pct"] <= 100).all()


# --- risk aggregation --------------------------------------------------------


def test_settled_risk_is_split_out_rather_than_dropped(data):
    """Excluding it silently would leave a risk manager hunting the difference."""
    grid = aggregate_risk(data, as_of=AS_OF).set_index(["book_id", "risk_metric"])
    row = grid.loc[("FX-TEST-01", "Delta_USD")]

    assert row["settled_usd"] == pytest.approx(2_178_000.0)
    assert row["open_usd"] != 0
    assert row["total_usd"] == pytest.approx(row["open_usd"] + row["settled_usd"])


def test_duration_is_never_summed(data):
    """A total duration is not a quantity that exists."""
    grid = aggregate_risk(data, as_of=AS_OF)

    assert "Duration" not in set(grid["risk_metric"])
    assert "Duration" in set(non_additive_metrics(data)["risk_metric"])


def test_additive_metrics_are_summed_per_book(data):
    grid = aggregate_risk(data, as_of=AS_OF)
    expected = data.risk[
        (data.risk["book_id"] == "RATES-TEST-01") & (data.risk["risk_metric"] == "DV01")
    ]["value_usd"].sum()

    total = grid[(grid["book_id"] == "RATES-TEST-01") & (grid["risk_metric"] == "DV01")][
        "total_usd"
    ].iloc[0]

    assert total == pytest.approx(expected)


def test_non_additive_metrics_stay_per_trade(data):
    tenors = non_additive_metrics(data)

    assert not tenors.empty
    assert "trade_id" in tenors.columns
    assert set(tenors["unit"]) == {"years"}


def _with(data, **replacements):
    return replace(data, **replacements)
