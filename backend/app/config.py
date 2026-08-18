"""Paths and reference constants shared across the backend."""

import os
from datetime import date
from pathlib import Path

# backend/app/config.py -> backend/app -> backend -> repo root
REPO_ROOT = Path(__file__).resolve().parents[2]

REPORTING_CCY = "USD"

# Reference "as of" date for position, risk and P&L purposes, per the data
# dictionary shipped alongside the extracts. The market data and FX files
# cover business days from HISTORY_START_DATE to AS_OF_DATE inclusive, which
# is what bounds the daily P&L replay.
AS_OF_DATE = date(2026, 8, 5)
HISTORY_START_DATE = date(2026, 7, 3)


def data_dir() -> Path:
    """Directory holding the four extracts.

    Resolved on every call rather than captured at import time, so that tests
    can redirect RAD_DATA_DIR at runtime without depending on module import
    order. Defaults to <repo>/data so the backend behaves identically whatever
    the current working directory is.
    """
    override = os.environ.get("RAD_DATA_DIR")
    return Path(override) if override else REPO_ROOT / "data"
