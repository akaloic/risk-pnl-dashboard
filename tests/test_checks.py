"""Market data and risk file quality checks."""

from datetime import date

import pandas as pd
import pytest

from app.checks import run_checks
from app.dataset import load_dataset
from app.issues import IssueCode, Severity

AS_OF = date(2026, 8, 5)


@pytest.fixture
def data():
    return load_dataset()


def _issues_for(issues, code):
    return [issue for issue in issues if issue.code == code]


def test_a_quote_timestamped_on_another_day_is_flagged(data):
    """A snapshot dated today carrying yesterday's timestamp is yesterday's price."""
    quotes = data.quotes.copy()
    stale = (quotes["instrument_id"] == "TST-CORP-2029") & (quotes["date"] == pd.Timestamp(AS_OF))
    quotes.loc[stale, "last_update_utc"] = pd.Timestamp("2026-08-04T09:05:00Z")

    issues = run_checks(_with(data, quotes=quotes), as_of=AS_OF)
    found = _issues_for(issues, IssueCode.STALE_QUOTE)

    assert [issue.entity_id for issue in found] == ["TST-CORP-2029@2026-08-05"]
    assert found[0].severity == Severity.WARNING


def test_quotes_timestamped_on_their_own_day_are_not_flagged(data):
    assert _issues_for(run_checks(data, as_of=AS_OF), IssueCode.STALE_QUOTE) == []


def test_duration_longer_than_the_remaining_life_is_flagged(data):
    """No modified duration can exceed the time left to maturity."""
    risk = data.risk.copy()
    row = (risk["trade_id"] == "FIX-001") & (risk["risk_metric"] == "Duration")
    risk.loc[row, "value"] = 40.0

    issues = run_checks(_with(data, risk=risk), as_of=AS_OF)
    found = _issues_for(issues, IssueCode.IMPLAUSIBLE_DURATION)

    assert [issue.entity_id for issue in found] == ["FIX-001"]
    assert "exceeds" in found[0].detail


def test_duration_far_below_the_tenor_is_flagged(data):
    """A placeholder value, not a measurement: the shape the four swaps have."""
    risk = data.risk.copy()
    row = (risk["trade_id"] == "FIX-001") & (risk["risk_metric"] == "Duration")
    risk.loc[row, "value"] = 0.9

    issues = run_checks(_with(data, risk=risk), as_of=AS_OF)
    found = _issues_for(issues, IssueCode.IMPLAUSIBLE_DURATION)

    assert [issue.entity_id for issue in found] == ["FIX-001"]
    assert "too low" in found[0].detail


def test_a_credible_duration_is_left_alone(data):
    """FIX-001 carries 4.5y against a 2030 maturity: unremarkable."""
    assert _issues_for(run_checks(data, as_of=AS_OF), IssueCode.IMPLAUSIBLE_DURATION) == []


def test_duration_is_never_used_to_produce_a_number(data):
    """The treatment must say so: quarantined, not merely noticed."""
    risk = data.risk.copy()
    row = (risk["trade_id"] == "FIX-001") & (risk["risk_metric"] == "Duration")
    risk.loc[row, "value"] = 0.9

    found = _issues_for(
        run_checks(_with(data, risk=risk), as_of=AS_OF), IssueCode.IMPLAUSIBLE_DURATION
    )

    assert "quarantined" in found[0].treatment


def test_an_instrument_quoted_but_never_traded_is_noted_as_benign(data):
    quotes = pd.concat(
        [
            data.quotes,
            data.quotes[data.quotes["instrument_id"] == "TST-BOND-2030"].assign(
                instrument_id="TST-BOND-2035"
            ),
        ],
        ignore_index=True,
    )

    found = _issues_for(
        run_checks(_with(data, quotes=quotes), as_of=AS_OF), IssueCode.QUOTE_WITHOUT_POSITION
    )

    assert [issue.entity_id for issue in found] == ["TST-BOND-2035"]
    assert found[0].severity == Severity.INFO


def test_a_price_series_contradicting_its_yield_series_is_flagged(data):
    """Price up while yield up implies a negative duration, which cannot be."""
    quotes = data.quotes.copy()
    bond = quotes["instrument_id"] == "TST-BOND-2030"
    quotes.loc[bond, "yield_pct"] = quotes.loc[bond, "px_mid"] / 50

    found = _issues_for(
        run_checks(_with(data, quotes=quotes), as_of=AS_OF), IssueCode.PRICE_YIELD_INCOHERENT
    )

    assert [issue.entity_id for issue in found] == ["TST-BOND-2030"]
    assert "negative" in found[0].detail


def test_a_coherent_price_and_yield_series_is_not_flagged(data):
    assert _issues_for(run_checks(data, as_of=AS_OF), IssueCode.PRICE_YIELD_INCOHERENT) == []


def test_checks_only_report_and_never_alter_the_data(data):
    before = data.quotes.copy()
    run_checks(data, as_of=AS_OF)

    pd.testing.assert_frame_equal(before, data.quotes)


def _with(data, **replacements):
    from dataclasses import replace

    return replace(data, **replacements)
