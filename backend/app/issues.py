"""The shared vocabulary for data quality findings.

Deliberately a leaf module: it holds no pandas logic and imports nothing from
the rest of the app, so every engine -- cleaning, positions, pricing,
reconciliation -- can report a finding without depending on any of the others.
That is what lets the data quality report be assembled from all of them at
once, with one set of codes that the panel on screen, the tests and
docs/DATA.md all name the same way.
"""

from enum import Enum

from pydantic import BaseModel


class Severity(str, Enum):
    """How much attention an issue needs, given the treatment applied to it.

    Graded by impact on the numbers rather than by how exotic the defect looks,
    so a risk manager scanning the report sees what would actually have moved a
    figure.
    """

    # Would have produced a materially wrong position, P&L or risk number, or
    # could not be treated automatically at all. Someone has to look.
    ERROR = "ERROR"
    # Genuine defect with a safe, deterministic treatment -- repaired, or
    # handled conservatively. Recorded so the source system still gets fixed.
    WARNING = "WARNING"
    # Observed, understood and harmless. Recorded so that the next person to
    # compare two files does not spend an afternoon rediscovering it.
    INFO = "INFO"


# Ordering used when the report is assembled: worst first, then stable by code
# and entity so the panel and the tests never see a shuffled list.
_SEVERITY_RANK = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}


class IssueCode(str, Enum):
    # Blotter-level defects, detected while cleaning the trade file.
    DUPLICATE_TRADE_ROW = "DUPLICATE_TRADE_ROW"
    CONFLICTING_TRADE_ROW = "CONFLICTING_TRADE_ROW"
    MALFORMED_TRADE_DATE = "MALFORMED_TRADE_DATE"
    UNREPAIRABLE_TRADE_DATE = "UNREPAIRABLE_TRADE_DATE"
    TRADE_DATE_AFTER_SETTLE_DATE = "TRADE_DATE_AFTER_SETTLE_DATE"
    NEGATIVE_QUANTITY_WITH_DIRECTION = "NEGATIVE_QUANTITY_WITH_DIRECTION"
    MISSING_SETTLE_DATE = "MISSING_SETTLE_DATE"

    # Settlement-state defects, detected while building positions.
    SETTLED_TRADE_MARKED_LIVE = "SETTLED_TRADE_MARKED_LIVE"
    SETTLEMENT_STATE_UNKNOWN = "SETTLEMENT_STATE_UNKNOWN"
    TERM_FX_SETTLE_BEFORE_MATURITY = "TERM_FX_SETTLE_BEFORE_MATURITY"

    # Inputs the pricing engine needed and did not find.
    MISSING_MARKET_DATA = "MISSING_MARKET_DATA"
    MISSING_SENSITIVITY = "MISSING_SENSITIVITY"

    # Market data and risk file quality.
    STALE_QUOTE = "STALE_QUOTE"
    IMPLAUSIBLE_DURATION = "IMPLAUSIBLE_DURATION"
    QUOTE_WITHOUT_POSITION = "QUOTE_WITHOUT_POSITION"
    PRICE_YIELD_INCOHERENT = "PRICE_YIELD_INCOHERENT"

    # Blotter against risk file.
    TRADE_WITHOUT_RISK = "TRADE_WITHOUT_RISK"
    RISK_WITHOUT_TRADE = "RISK_WITHOUT_TRADE"
    VALUE_USD_MISMATCH = "VALUE_USD_MISMATCH"
    SETTLED_TRADE_CARRIES_RISK = "SETTLED_TRADE_CARRIES_RISK"


class DataQualityIssue(BaseModel):
    """One finding, with the treatment that was applied to it.

    `treatment` is not decoration: the report exists so that a number can be
    challenged and explained, which means every issue has to say what the tool
    did about it, not merely that something was wrong.
    """

    code: IssueCode
    severity: Severity
    entity_type: str
    entity_id: str
    detail: str
    treatment: str


def merge(*groups: list[DataQualityIssue]) -> list[DataQualityIssue]:
    """Combine issue lists from several engines into one ordered report.

    The single place ordering is decided, so that adding a new check later
    cannot quietly change how the panel is sorted.
    """
    combined = [issue for group in groups for issue in group]
    return sorted(
        combined,
        key=lambda issue: (
            _SEVERITY_RANK[issue.severity],
            issue.code.value,
            issue.entity_id,
        ),
    )
