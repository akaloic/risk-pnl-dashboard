"""The complete data quality report, assembled from every engine that finds one.

Findings arise in five places -- cleaning the blotter, deriving settlement
state, valuing the book, checking the market data, and reconciling against the
risk file -- and a desk needs to see them in one list, ordered by how much they
would have moved a number.

Keeping the assembly here rather than in the route means the report can be
tested without a web server, and that the panel cannot quietly diverge from
what the engines actually reported.
"""

from datetime import date

from app.analytics import daily_pnl_series
from app.checks import run_checks
from app.config import AS_OF_DATE
from app.dataset import Dataset
from app.issues import DataQualityIssue, Severity, merge
from app.positions import build_positions
from app.reconciliation import reconcile


def full_quality_report(data: Dataset, as_of: date = AS_OF_DATE) -> list[DataQualityIssue]:
    """Every finding, deduplicated and ordered worst first.

    The valuation issues come from the daily replay rather than from a single
    valuation, so a trade that cannot be priced on any day of the month is
    caught even if it happens to be priceable on the as-of date.
    """
    _, valuation_issues = daily_pnl_series(data, as_of=as_of)

    return merge(
        data.issues,
        build_positions(data.trades, as_of=as_of).issues,
        valuation_issues,
        run_checks(data, as_of=as_of),
        reconcile(data, as_of=as_of),
    )


def severity_counts(issues: list[DataQualityIssue]) -> dict[str, int]:
    """How many findings of each severity, for the panel's header."""
    return {
        severity.value: sum(1 for issue in issues if issue.severity == severity)
        for severity in Severity
    }
