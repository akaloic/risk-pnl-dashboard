"""Typed pandas loaders for the four extracts.

These loaders stay deliberately close to the source files: they read a CSV,
coerce dtypes, reject values outside the documented domains, and normalize
risk metric spellings. They do NOT deduplicate rows, repair malformed dates or
correct signs -- those are blotter quality issues that need an audit trail, and
they are handled by a dedicated data-quality layer applied on top of the raw
frames returned here. Keeping the two apart means every downstream module can
choose the raw extract (to reconcile against the source system) or the cleaned
one (to compute a number), and that the cleaning is always visible rather than
buried inside a read_csv call.
"""

from enum import Enum
from pathlib import Path

import pandas as pd

from app.config import data_dir
from app.models import AssetClass, Direction, PriceType, ProductType, RiskMetric

# The glossary spells every USD-denominated metric with an underscore
# (JTD_USD, CS01_USD, Delta_USD). Match on a punctuation- and case-insensitive
# key so an export that drops the underscore still lands on the canonical name
# instead of opening a second bucket in every risk aggregation.
_RISK_METRIC_BY_KEY = {m.value.replace("_", "").upper(): m.value for m in RiskMetric}


def _canonicalize_risk_metric(raw: str) -> str:
    key = str(raw).strip().replace("_", "").replace(" ", "").upper()
    try:
        return _RISK_METRIC_BY_KEY[key]
    except KeyError:
        raise ValueError(
            f"Unrecognized risk_metric {raw!r}; expected one of "
            f"{sorted(m.value for m in RiskMetric)}"
        ) from None


def _validate_domains(df: pd.DataFrame, source: str, columns: dict[str, type[Enum]]) -> None:
    """Fail loudly when a column carries a value outside its documented domain.

    A new product type or asset class arriving unannounced is exactly the kind
    of change that would otherwise be silently dropped by a downstream filter
    and quietly understate the desk's P&L.
    """
    for column, enum_cls in columns.items():
        allowed = {member.value for member in enum_cls}
        unexpected = sorted(set(df[column].dropna().unique()) - allowed)
        if unexpected:
            raise ValueError(
                f"{source}: column {column!r} carries undocumented value(s) "
                f"{unexpected}; expected a subset of {sorted(allowed)}"
            )


def _require(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(
            f"{path} not found. Drop the confidential extracts into {path.parent}/ "
            "(see data/README.md), or set RAD_DATA_DIR to point at another snapshot."
        )
    return path


def load_trades_raw(path: Path | None = None) -> pd.DataFrame:
    path = path or data_dir() / "trades.csv"
    df = pd.read_csv(_require(path), dtype={"trade_id": str, "book_id": str})

    _validate_domains(
        df,
        path.name,
        {
            "asset_class": AssetClass,
            "product_type": ProductType,
            "direction": Direction,
        },
    )

    # Strict ISO parsing on purpose. Part of the blotter carries trade_date as
    # MM/DD/YYYY; those rows must surface as NaT here so the data-quality layer
    # can repair them explicitly and report what it did, rather than have a
    # permissive parser guess at the day/month order behind our back.
    #
    # The parse destroys the offending text, so keep trade_date's original
    # string alongside it: the repair needs the source value. The data-quality
    # layer drops this column once it has run.
    df["trade_date_raw"] = df["trade_date"].astype(str)

    for col in ("trade_date", "settle_date", "maturity_date"):
        df[col] = pd.to_datetime(df[col], format="%Y-%m-%d", errors="coerce")

    for col in ("notional", "quantity", "trade_price"):
        df[col] = pd.to_numeric(df[col], errors="raise")

    return df


def load_market_data_raw(path: Path | None = None) -> pd.DataFrame:
    path = path or data_dir() / "market_data.csv"
    df = pd.read_csv(_require(path), dtype={"instrument_id": str})

    _validate_domains(df, path.name, {"asset_class": AssetClass, "price_type": PriceType})

    df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d", errors="raise")
    df["last_update_utc"] = pd.to_datetime(df["last_update_utc"], format="ISO8601", utc=True)

    numeric_cols = (
        "price",
        "yield_pct",
        "spread_bps",
        "implied_vol_pct",
        "px_bid",
        "px_ask",
        "px_mid",
    )
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def load_risk_sensitivities_raw(path: Path | None = None) -> pd.DataFrame:
    path = path or data_dir() / "risk_sensitivities.csv"
    df = pd.read_csv(_require(path), dtype={"trade_id": str, "instrument_id": str})

    df["risk_metric"] = df["risk_metric"].map(_canonicalize_risk_metric)

    df["as_of_date"] = pd.to_datetime(df["as_of_date"], format="%Y-%m-%d", errors="raise")
    df["computation_timestamp"] = pd.to_datetime(
        df["computation_timestamp"], format="ISO8601", utc=True
    )
    df["value"] = pd.to_numeric(df["value"], errors="raise")
    df["value_usd"] = pd.to_numeric(df["value_usd"], errors="raise")

    return df


def load_fx_rates_raw(path: Path | None = None) -> pd.DataFrame:
    path = path or data_dir() / "fx_rates.csv"
    df = pd.read_csv(_require(path))
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d", errors="raise")
    df["spot_rate"] = pd.to_numeric(df["spot_rate"], errors="raise")

    return df


def to_records(df: pd.DataFrame) -> list[dict]:
    """Convert a DataFrame to plain dicts with real None in place of NaN/NaT.

    Assigning None into a datetime64 column is silently coerced back to NaT by
    pandas, which then fails pydantic validation and json serialisation alike.
    Casting to object first is what makes the null survive.
    """
    obj = df.astype(object)
    return obj.where(obj.notna(), None).to_dict(orient="records")
