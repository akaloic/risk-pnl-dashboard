"""Canonical domain schema for the four extracts.

The enums pin down the categorical domains documented in the data dictionary.
Loaders validate every ingested frame against them, so an unexpected product
type or risk metric fails loudly at ingest instead of quietly skewing a P&L
number downstream. The models describe one row of each extract and are reused
as API response schemas, which keeps the wire format from drifting away from
the shape of the source files.
"""

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel


class AssetClass(str, Enum):
    RATES = "RATES"
    CREDIT = "CREDIT"
    FX = "FX"
    EQUITY = "EQUITY"


class ProductType(str, Enum):
    IRS = "IRS"
    GOVT_BOND = "GOVT_BOND"
    CORP_BOND = "CORP_BOND"
    CDS = "CDS"
    FX_SPOT = "FX_SPOT"
    FX_FORWARD = "FX_FORWARD"
    FX_NDF = "FX_NDF"
    EQ_OPTION = "EQ_OPTION"
    EQ_FUTURE = "EQ_FUTURE"


class Direction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    PAY = "PAY"
    RECEIVE = "RECEIVE"


# Canonical risk metric names, matching the glossary in the data dictionary.
# loaders._canonicalize_risk_metric maps any raw spelling onto these (a feed
# that drops the underscore, or varies casing, must not silently create a
# second bucket in every aggregation keyed on risk_metric).
class RiskMetric(str, Enum):
    DV01 = "DV01"
    DURATION = "Duration"
    SPREAD01 = "Spread01"
    CS01_USD = "CS01_USD"
    JTD_USD = "JTD_USD"
    DELTA_USD = "Delta_USD"
    GAMMA_USD = "Gamma_USD"
    VEGA_USD = "Vega_USD"
    THETA_USD = "Theta_USD"


class PriceType(str, Enum):
    CLEAN = "CLEAN"
    LAST = "LAST"
    PAR_RATE = "PAR_RATE"
    SPREAD = "SPREAD"


class Trade(BaseModel):
    trade_id: str
    book_id: str
    trader_id: str
    trade_date: date
    settle_date: date | None = None
    asset_class: AssetClass
    product_type: ProductType
    instrument_id: str
    instrument_description: str
    currency: str
    notional: float
    quantity: float
    trade_price: float
    direction: Direction
    # Status as carried by the blotter, kept as free text: the dictionary does
    # not constrain it, and the desk's own "settled vs open" view is derived
    # from settle_date rather than trusted from this column.
    status: str
    counterparty_id: str
    counterparty_name: str
    maturity_date: date | None = None
    bloomberg_id: str | None = None
    internal_ref: str | None = None


class MarketQuote(BaseModel):
    date: date
    instrument_id: str
    instrument_description: str
    asset_class: AssetClass
    price: float | None = None
    yield_pct: float | None = None
    spread_bps: float | None = None
    implied_vol_pct: float | None = None
    px_bid: float | None = None
    px_ask: float | None = None
    px_mid: float | None = None
    price_type: PriceType
    source: str
    last_update_utc: datetime


class RiskSensitivity(BaseModel):
    as_of_date: date
    trade_id: str
    book_id: str
    instrument_id: str
    risk_metric: RiskMetric
    value: float
    ccy: str
    value_usd: float
    unit: str
    computation_timestamp: datetime
    notes: str | None = None


class FxRate(BaseModel):
    date: date
    ccy_pair: str
    base_ccy: str
    quote_ccy: str
    spot_rate: float
    source: str
