"""Blotter cleaning: detect, treat, and report -- never silently swallow.

Operational extracts arrive with defects. The rule applied throughout this
module is that a defect is either repaired with a treatment we can defend in
words, or escalated untreated -- but it is always recorded. Nothing is quietly
dropped on the way to a P&L number, because the figure a trader disputes at
07:30 is only useful if we can say exactly what the tool changed underneath it.

Scope is the trade file alone. Checks that need another extract to make sense
belong to the engine that joins them: settlement state lives with positions,
valuation consistency with pricing. They all report through the shared
vocabulary in app.issues.
"""

import re
from datetime import date
from typing import NamedTuple

import pandas as pd

from app.issues import DataQualityIssue, IssueCode, Severity, merge
from app.models import Direction


class CleanedBlotter(NamedTuple):
    trades: pd.DataFrame
    issues: list[DataQualityIssue]


# Direction is the source of truth for whether a position is long or short.
# Quantity is treated as a magnitude, so that a blotter which encodes the side
# twice (negative quantity *and* a SELL) cannot cancel itself back to a long.
SIGN_BY_DIRECTION = {
    Direction.BUY.value: 1,
    Direction.RECEIVE.value: 1,
    Direction.SELL.value: -1,
    Direction.PAY.value: -1,
}

_SLASHED_DATE = re.compile(r"^\s*(\d{1,2})/(\d{1,2})/(\d{4})\s*$")


def _try_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _parse_slashed_date(text: str) -> tuple[date | None, str]:
    """Parse a slash-separated date, refusing to guess when it is ambiguous.

    The rows seen in this blotter are US-formatted (MM/DD/YYYY), but rather
    than hard-code that reading we accept it only when the alternative is
    impossible -- 07/28/2026 has no 28th month, so it can only be 28 July.
    A value like 07/08/2026 stays unrepaired and is escalated instead: silently
    picking a convention there would move a trade by a month, and a wrong date
    is harder to spot downstream than a missing one.
    """
    match = _SLASHED_DATE.match(text)
    if not match:
        return None, f"{text!r} is not a recognised date format"

    first, second, year = int(match[1]), int(match[2]), int(match[3])
    month_first = _try_date(year, first, second)
    day_first = _try_date(year, second, first)

    if month_first and day_first and month_first != day_first:
        return None, (
            f"{text!r} is ambiguous: valid as both MM/DD ({month_first}) and DD/MM ({day_first})"
        )

    parsed = month_first or day_first
    if parsed is None:
        return None, f"{text!r} is not a valid calendar date"

    convention = "MM/DD/YYYY" if month_first else "DD/MM/YYYY"
    return parsed, f"{text!r} read as {convention}"


def _drop_duplicate_rows(df: pd.DataFrame, issues: list[DataQualityIssue]) -> pd.DataFrame:
    """Drop rows that repeat another row in full, and report each one.

    An exact repeat is a re-delivered blotter line, not a second trade: the
    risk file carries a single set of sensitivities for the trade id, so
    keeping both rows would double its P&L while leaving its risk unchanged
    and break the P&L/risk reconciliation.
    """
    duplicated = df.duplicated(keep="first")
    for trade_id, count in df.loc[duplicated, "trade_id"].value_counts().items():
        issues.append(
            DataQualityIssue(
                code=IssueCode.DUPLICATE_TRADE_ROW,
                severity=Severity.ERROR,
                entity_type="trade",
                entity_id=str(trade_id),
                detail=(
                    f"{count} exact duplicate row(s) in the blotter; the risk file "
                    "carries a single set of sensitivities for this trade id"
                ),
                treatment=(
                    "Duplicate row(s) dropped, first occurrence kept. Keeping them "
                    "would double this trade's P&L against unchanged risk."
                ),
            )
        )
    return df.loc[~duplicated].copy()


def _resolve_conflicting_rows(df: pd.DataFrame, issues: list[DataQualityIssue]) -> pd.DataFrame:
    """Report trade ids that appear more than once with *different* contents.

    Deliberately separate from the exact-duplicate case: two rows disagreeing
    on the same trade id is an unresolved booking, not a redelivery, and there
    is no defensible way to pick a winner automatically.
    """
    repeated = df["trade_id"].value_counts()
    for trade_id in repeated[repeated > 1].index:
        issues.append(
            DataQualityIssue(
                code=IssueCode.CONFLICTING_TRADE_ROW,
                severity=Severity.ERROR,
                entity_type="trade",
                entity_id=str(trade_id),
                detail=(
                    f"{repeated[trade_id]} rows share this trade id but differ in "
                    "content; the correct economics cannot be determined from the extract"
                ),
                treatment=(
                    "First occurrence kept so the blotter stays keyed by trade id. "
                    "Needs resolution in the source system."
                ),
            )
        )
    return df.loc[~df["trade_id"].duplicated(keep="first")].copy()


def _repair_trade_dates(df: pd.DataFrame, issues: list[DataQualityIssue]) -> pd.DataFrame:
    """Repair non-ISO trade dates left as NaT by the strict parse."""
    unparsed = df["trade_date"].isna()

    for idx in df.index[unparsed]:
        trade_id = str(df.at[idx, "trade_id"])
        raw = str(df.at[idx, "trade_date_raw"]).strip()

        if raw in ("", "nan", "NaT", "None"):
            issues.append(
                DataQualityIssue(
                    code=IssueCode.UNREPAIRABLE_TRADE_DATE,
                    severity=Severity.ERROR,
                    entity_type="trade",
                    entity_id=trade_id,
                    detail="trade_date is empty in the extract",
                    treatment="Left null; the trade cannot be aged or replayed by trade date.",
                )
            )
            continue

        parsed, note = _parse_slashed_date(raw)
        if parsed is None:
            issues.append(
                DataQualityIssue(
                    code=IssueCode.UNREPAIRABLE_TRADE_DATE,
                    severity=Severity.ERROR,
                    entity_type="trade",
                    entity_id=trade_id,
                    detail=f"trade_date could not be repaired: {note}",
                    treatment="Left null rather than guessed at; needs a human decision.",
                )
            )
            continue

        df.at[idx, "trade_date"] = pd.Timestamp(parsed)
        issues.append(
            DataQualityIssue(
                code=IssueCode.MALFORMED_TRADE_DATE,
                severity=Severity.WARNING,
                entity_type="trade",
                entity_id=trade_id,
                detail=f"trade_date not ISO-8601: {note}, rest of the file is ISO",
                treatment=f"Normalised to {parsed.isoformat()}.",
            )
        )

    return df


def _check_date_coherence(df: pd.DataFrame, issues: list[DataQualityIssue]) -> None:
    """Cross-check trade_date against settle_date.

    This is what validates a date repair rather than trusting it: a trade that
    settles before it was executed means the reading we chose was wrong.
    """
    both = df["trade_date"].notna() & df["settle_date"].notna()
    inverted = both & (df["trade_date"] > df["settle_date"])

    for idx in df.index[inverted]:
        trade_date = df.at[idx, "trade_date"].date()
        settle_date = df.at[idx, "settle_date"].date()
        issues.append(
            DataQualityIssue(
                code=IssueCode.TRADE_DATE_AFTER_SETTLE_DATE,
                severity=Severity.ERROR,
                entity_type="trade",
                entity_id=str(df.at[idx, "trade_id"]),
                detail=f"trade_date {trade_date} is after settle_date {settle_date}",
                treatment="Both dates left as-is; flagged for investigation.",
            )
        )


def _flag_missing_settle_dates(df: pd.DataFrame, issues: list[DataQualityIssue]) -> None:
    """Report blank settlement dates.

    Reported rather than repaired: settle_date is what decides whether a trade
    is still an open position or settled cash, and inventing one would quietly
    move a trade in or out of the book.
    """
    for idx in df.index[df["settle_date"].isna()]:
        issues.append(
            DataQualityIssue(
                code=IssueCode.MISSING_SETTLE_DATE,
                severity=Severity.WARNING,
                entity_type="trade",
                entity_id=str(df.at[idx, "trade_id"]),
                detail="settle_date is blank in the extract",
                treatment=(
                    "Left null and treated as an open position, since settlement "
                    "cannot be confirmed from the extract."
                ),
            )
        )


def _normalise_quantity_sign(df: pd.DataFrame, issues: list[DataQualityIssue]) -> pd.DataFrame:
    """Make quantity a magnitude and let direction carry the side.

    A row with a negative quantity *and* a SELL encodes the short twice. Taken
    literally that is a long position, so the sign of the P&L flips -- the kind
    of defect that is invisible on a screen until the number is badly wrong.
    """
    negative = df["quantity"] < 0

    for idx in df.index[negative]:
        direction = str(df.at[idx, "direction"])
        quantity = df.at[idx, "quantity"]
        issues.append(
            DataQualityIssue(
                code=IssueCode.NEGATIVE_QUANTITY_WITH_DIRECTION,
                severity=Severity.ERROR,
                entity_type="trade",
                entity_id=str(df.at[idx, "trade_id"]),
                detail=(
                    f"quantity {quantity:g} is negative while direction is {direction}: "
                    "the side is encoded twice"
                ),
                treatment=(
                    f"Quantity taken as magnitude {abs(quantity):g}; direction "
                    f"{direction} governs the sign."
                ),
            )
        )

    df["quantity"] = df["quantity"].abs()
    return df


def clean_trades(raw: pd.DataFrame) -> CleanedBlotter:
    """Return a blotter safe to price, plus every issue found getting there.

    Order matters: duplicates go first so later checks do not report the same
    defect twice, and the date coherence check runs after the repair so it can
    validate the repaired value.

    Helpers named _drop/_resolve/_repair/_normalise change the frame; those
    named _check/_flag only observe it.
    """
    issues: list[DataQualityIssue] = []

    df = raw.copy()
    df = _drop_duplicate_rows(df, issues)
    df = _resolve_conflicting_rows(df, issues)
    df = _repair_trade_dates(df, issues)
    _check_date_coherence(df, issues)
    _flag_missing_settle_dates(df, issues)
    df = _normalise_quantity_sign(df, issues)

    df["direction_sign"] = df["direction"].map(SIGN_BY_DIRECTION).astype(int)

    df = df.drop(columns=["trade_date_raw"]).reset_index(drop=True)

    return CleanedBlotter(trades=df, issues=merge(issues))
