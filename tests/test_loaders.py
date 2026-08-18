"""Loader-level tests: dtype coercion, domain validation, metric normalization."""

import pandas as pd
import pytest

from app.config import data_dir
from app.loaders import (
    load_fx_rates_raw,
    load_market_data_raw,
    load_risk_sensitivities_raw,
    load_trades_raw,
    to_records,
)
from app.models import FxRate, MarketQuote, RiskSensitivity, Trade


def test_data_dir_follows_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("RAD_DATA_DIR", str(tmp_path))
    assert data_dir() == tmp_path


def test_missing_file_names_the_path_and_how_to_fix_it(tmp_path, monkeypatch):
    monkeypatch.setenv("RAD_DATA_DIR", str(tmp_path))
    with pytest.raises(FileNotFoundError, match="RAD_DATA_DIR"):
        load_trades_raw()


def test_trades_load_with_expected_dtypes():
    df = load_trades_raw()

    assert len(df) == 4
    assert df["trade_date"].dtype == "datetime64[ns]"
    assert df["notional"].dtype.kind in "if"
    assert df["quantity"].dtype.kind in "if"


def test_malformed_trade_date_is_left_as_nat_for_the_dq_layer():
    """Non-ISO dates must not be silently guessed at by the parser.

    FIX-003 carries 07/28/2026. The loader's job is to surface that as NaT;
    repairing it (and reporting the repair) belongs to the data-quality layer.
    """
    df = load_trades_raw().set_index("trade_id")

    assert pd.isna(df.loc["FIX-003", "trade_date"])
    assert df["trade_date"].isna().sum() == 1
    assert df.loc["FIX-001", "trade_date"] == pd.Timestamp("2026-07-01")


def test_blank_settle_date_is_distinct_from_a_malformed_one():
    df = load_trades_raw().set_index("trade_id")

    # Every fixture row has a settle date; a blank one would also read as NaT,
    # which is why the DQ layer reports missing and malformed dates separately.
    assert df["settle_date"].notna().all()


def test_risk_metric_spelling_is_normalized_onto_the_glossary():
    """DeltaUSD in the file must land on the canonical Delta_USD.

    Otherwise the same sensitivity splits across two buckets in every
    aggregation keyed on risk_metric, and the risk grid silently under-reports.
    """
    df = load_risk_sensitivities_raw()

    assert "DeltaUSD" not in set(df["risk_metric"])
    assert set(df["risk_metric"]) == {"DV01", "Duration", "Delta_USD"}
    assert (df.set_index("trade_id").loc["FIX-003", "risk_metric"]) == "Delta_USD"


def test_unknown_risk_metric_is_rejected(tmp_path, monkeypatch):
    src = (data_dir() / "risk_sensitivities.csv").read_text()
    broken = src.replace("Duration", "Convexity")
    (tmp_path / "risk_sensitivities.csv").write_text(broken)
    monkeypatch.setenv("RAD_DATA_DIR", str(tmp_path))

    with pytest.raises(ValueError, match="Unrecognized risk_metric"):
        load_risk_sensitivities_raw()


def test_undocumented_product_type_is_rejected(tmp_path, monkeypatch):
    """A new product arriving unannounced must fail at ingest, not downstream.

    Silently dropping it in a later filter would understate the desk's P&L.
    """
    src = (data_dir() / "trades.csv").read_text()
    broken = src.replace("EQ_FUTURE", "EQ_VARIANCE_SWAP")
    (tmp_path / "trades.csv").write_text(broken)
    monkeypatch.setenv("RAD_DATA_DIR", str(tmp_path))

    with pytest.raises(ValueError, match="EQ_VARIANCE_SWAP"):
        load_trades_raw()


def test_market_data_and_fx_load_with_parsed_timestamps():
    md = load_market_data_raw()
    fx = load_fx_rates_raw()

    assert md["last_update_utc"].dt.tz is not None
    assert md["date"].dtype == "datetime64[ns]"
    assert len(fx) == 4
    assert fx.set_index(["date", "ccy_pair"]).loc[
        (pd.Timestamp("2026-08-05"), "USDJPY"), "spot_rate"
    ] == 150.0


def test_empty_numeric_cells_become_nan_not_zero():
    """A par-rate row has no price; it must not read as a price of 0.0."""
    md = load_market_data_raw()
    irs = md[md["instrument_id"] == "TST-IRS-5Y"]

    assert irs["price"].isna().all()
    assert irs["yield_pct"].notna().all()


def test_to_records_yields_none_rather_than_nat():
    records = to_records(load_trades_raw())
    fix_003 = next(r for r in records if r["trade_id"] == "FIX-003")

    assert fix_003["trade_date"] is None
    assert fix_003["bloomberg_id"] is None


def test_every_extract_validates_against_its_model():
    """The models are the contract; prove the real column layout satisfies it."""
    trades = load_trades_raw()
    for record in to_records(trades[trades["trade_date"].notna()]):
        Trade.model_validate(record)

    for record in to_records(load_market_data_raw()):
        MarketQuote.model_validate(record)

    for record in to_records(load_risk_sensitivities_raw()):
        RiskSensitivity.model_validate(record)

    for record in to_records(load_fx_rates_raw()):
        FxRate.model_validate(record)
