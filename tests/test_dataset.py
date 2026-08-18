"""Composition-root tests: one assembly, one set of findings."""

import pandas as pd

from app.dataset import load_dataset
from app.positions import build_positions


def test_dataset_exposes_a_cleaned_blotter():
    data = load_dataset()

    assert data.trades["trade_id"].is_unique
    assert (data.trades["quantity"] >= 0).all()
    assert "direction_sign" in data.trades.columns


def test_raw_blotter_is_kept_for_reconciliation():
    """Reconciliation has to compare against the file as delivered."""
    data = load_dataset()

    assert len(data.raw_trades) > len(data.trades)
    assert not data.raw_trades["trade_id"].is_unique


def test_cleaning_findings_are_carried_on_the_dataset():
    data = load_dataset()

    assert data.issues
    assert {issue.code.value for issue in data.issues} >= {"DUPLICATE_TRADE_ROW"}


def test_anomalies_are_reported_once_not_once_per_valuation_date():
    """The reason the assembly is centralised.

    Re-cleaning per date would repeat the same duplicate-trade finding for
    every business day in the replay window.
    """
    data = load_dataset()
    duplicates = [i for i in data.issues if i.code.value == "DUPLICATE_TRADE_ROW"]

    assert len(duplicates) == 1
    assert len(data.business_days) > 1


def test_business_days_intersect_quotes_and_fx():
    """A day priced without a rate to convert it is not a reportable day."""
    data = load_dataset()

    quoted = set(data.quotes["date"].unique())
    assert set(data.business_days) <= quoted
    assert set(data.business_days) <= set(data.fx.dates)


def test_dataset_drives_the_positions_engine_unchanged():
    """The engines take the dataset's frames without further preparation."""
    data = load_dataset()

    book = build_positions(data.trades, as_of=pd.Timestamp("2026-08-05").date())

    assert not book.positions.empty
    assert book.positions["trade_ids"].map(len).sum() == len(data.trades)


def test_override_directory_is_honoured(tmp_path, monkeypatch):
    """An explicit path wins over the environment, for one-off snapshots."""
    from app.config import data_dir

    for name in ("trades.csv", "market_data.csv", "risk_sensitivities.csv", "fx_rates.csv"):
        (tmp_path / name).write_bytes((data_dir() / name).read_bytes())
    monkeypatch.setenv("RAD_DATA_DIR", "/nonexistent")

    data = load_dataset(data_dir=tmp_path)

    assert not data.trades.empty
