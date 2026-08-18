"""Mark-to-market P&L, one method per product class.

The five methodologies the desk uses look different but share a shape: each
product has a *level* that moves, and P&L is that move multiplied by a scale.

    bond      clean price      (price - ref)/100 x face x side
    swap      par rate         -(rate - ref) in bp x DV01
    CDS       spread           (spread - ref) in bp x CS01
    FX        spot rate        (rate - ref) x notional x side, in the quote ccy
    equity    index points     (price - ref) x contracts x multiplier x side

Writing it that way keeps each product's economics in one short function that
can be read and checked on its own, and lets the same engine produce both the
since-inception figure (reference = the traded level) and any daily move
(reference = the previous close), which is what the daily replay needs.

Two sign conventions matter and neither is stated in the extracts, so both were
read off the data. DV01 is positive for a long-duration position -- a bought
bond or a received-fixed swap -- so the swap P&L carries a minus: rates falling
is a gain for the receiver. CS01 is positive for bought protection, which gains
when spreads widen, so the credit P&L does not. Getting either backwards flips
the sign of a book's P&L while leaving it entirely plausible on screen.

FX is priced from the trade's own notional and the published spot, not from the
risk file's Delta_USD. The two agree where the risk file is consistent, and a
test asserts that; but the risk file was computed off a snapshot we were not
given, so deriving exposure from the blotter keeps the P&L reproducible from
the market data alone. market_data.csv carries no FX rows at all -- its asset
class domain is RATES, CREDIT and EQUITY -- so FX levels can only come from
fx_rates.csv.

Equity trades book a notional of zero, so their size is quantity x multiplier
and nothing else; a notional-driven valuation would report them as flat.
"""

from collections.abc import Callable
from datetime import date
from enum import Enum
from typing import NamedTuple

import pandas as pd
from pydantic import BaseModel

from app.config import AS_OF_DATE, REPORTING_CCY
from app.contracts import multiplier_for
from app.dataset import Dataset
from app.issues import DataQualityIssue, IssueCode, Severity, merge
from app.models import AssetClass, ProductType
from app.positions import closing_dates


class PnLMethod(str, Enum):
    BOND_CLEAN_PRICE = "BOND_CLEAN_PRICE"
    SWAP_DV01 = "SWAP_DV01"
    CDS_CS01 = "CDS_CS01"
    FX_RATE_MOVE = "FX_RATE_MOVE"
    EQUITY_CONTRACT = "EQUITY_CONTRACT"


class TradePnL(BaseModel):
    """P&L for one trade, with the inputs that produced it.

    The levels and the method are carried alongside the number so a trader can
    see what the figure was computed from without opening the source files --
    a P&L nobody can take apart is a P&L nobody will trust.
    """

    trade_id: str
    book_id: str
    asset_class: AssetClass
    product_type: ProductType
    instrument_id: str
    currency: str
    method: PnLMethod
    valuation_date: date
    reference_level: float
    current_level: float
    pnl_ccy: float
    pnl_currency: str
    pnl_usd: float


class PnLResult(NamedTuple):
    trades: pd.DataFrame
    issues: list[DataQualityIssue]


# --- the level each product moves on -----------------------------------------

# Which market_data column carries the level for each product, and hence what
# "the market moved" means for it. FX is absent on purpose: it is not in
# market_data.csv and is read from the FX grid instead.
_LEVEL_COLUMN = {
    ProductType.GOVT_BOND.value: "px_mid",
    ProductType.CORP_BOND.value: "px_mid",
    ProductType.IRS.value: "yield_pct",
    ProductType.CDS.value: "spread_bps",
    ProductType.EQ_OPTION.value: "px_mid",
    ProductType.EQ_FUTURE.value: "px_mid",
}


class _Levels:
    """Point lookup for market levels, built once per valuation run."""

    def __init__(self, data: Dataset):
        self._quotes: dict[tuple[str, pd.Timestamp], pd.Series] = {
            (row.instrument_id, row.date): row for row in data.quotes.itertuples(index=False)
        }
        self._fx = data.fx

    def market(self, trade: pd.Series, on: date) -> float | None:
        product = trade["product_type"]

        if product in _FX_PRODUCTS:
            try:
                return self._fx.rate(trade["instrument_id"], on)
            except KeyError:
                return None

        quote = self._quotes.get((trade["instrument_id"], pd.Timestamp(on)))
        if quote is None:
            return None

        level = getattr(quote, _LEVEL_COLUMN[product])
        return None if pd.isna(level) else float(level)


_FX_PRODUCTS = {
    ProductType.FX_SPOT.value,
    ProductType.FX_FORWARD.value,
    ProductType.FX_NDF.value,
}


# --- one pricer per product class --------------------------------------------


class _Inputs:
    """Everything a pricer needs besides the trade and the level move.

    Passed explicitly rather than held in module state: the API values the book
    on several dates concurrently, and a shared mutable lookup would let one
    request read another's currencies.
    """

    def __init__(self, data: Dataset):
        self._risk: dict[tuple[str, str], pd.Series] = {
            (row.trade_id, row.risk_metric): row for row in data.risk.itertuples(index=False)
        }
        self._pairs = {
            pair: data.fx.pair_currencies(pair)
            for pair in data.trades.loc[
                data.trades["asset_class"] == AssetClass.FX.value, "instrument_id"
            ].unique()
        }

    def sensitivity(self, trade_id: str, metric: str) -> pd.Series:
        try:
            return self._risk[(trade_id, metric)]
        except KeyError:
            raise LookupError(metric) from None

    def quote_currency(self, ccy_pair: str) -> str:
        return self._pairs[ccy_pair][1]


# Each returns (amount, currency of that amount) for a given level move.
Pricer = Callable[[pd.Series, float, _Inputs], tuple[float, str]]


def _price_bond(trade: pd.Series, move: float, inputs: _Inputs) -> tuple[float, str]:
    """Clean price is quoted per 100, so the move is a percentage of face."""
    return move / 100.0 * trade["notional"] * trade["direction_sign"], trade["currency"]


def _price_swap(trade: pd.Series, move: float, inputs: _Inputs) -> tuple[float, str]:
    """DV01 already carries the side: positive is long duration.

    Hence the minus. A received-fixed swap has a positive DV01 and gains when
    the par rate falls, so applying the move without negating it would report
    every rates position with its P&L inverted.
    """
    sensitivity = inputs.sensitivity(trade["trade_id"], "DV01")
    move_bp = move * 100.0
    return -move_bp * float(sensitivity.value), str(sensitivity.ccy)


def _price_cds(trade: pd.Series, move: float, inputs: _Inputs) -> tuple[float, str]:
    """CS01 is positive for bought protection, which gains as spreads widen.

    The opposite convention to DV01, and the reason these are two functions
    rather than one shared "sensitivity x move".
    """
    sensitivity = inputs.sensitivity(trade["trade_id"], "CS01_USD")
    return move * float(sensitivity.value_usd), REPORTING_CCY


def _price_fx(trade: pd.Series, move: float, inputs: _Inputs) -> tuple[float, str]:
    """P&L on an FX trade accrues in the quote currency of the pair.

    Forwards and NDFs are marked on the same spot move as a spot trade, which
    is an approximation and the largest one in this engine. fx_rates.csv
    carries a single `spot_rate` per pair per day -- no forward points, no
    tenor curve -- so the interest-rate differential between the two legs
    cannot be marked and is simply absent from the figure. Six term trades are
    valued this way and they carry 267k USD, around 60% of the desk's total,
    so the size of what is missing deserves stating rather than burying.

    The error is the change in the forward points over the holding period, not
    the points themselves: both the reference and the current level are spot,
    so a parallel carry that does not move cancels out. It is bounded by the
    rate differential on pairs like USDKRW and USDCNH, and closing it needs a
    forward curve the extract does not contain.
    """
    quote_ccy = inputs.quote_currency(trade["instrument_id"])
    return move * trade["notional"] * trade["direction_sign"], quote_ccy


def _price_equity(trade: pd.Series, move: float, inputs: _Inputs) -> tuple[float, str]:
    """Size is contracts x point value; the booked notional is zero."""
    multiplier = multiplier_for(trade["instrument_id"])
    return (
        move * trade["quantity"] * multiplier * trade["direction_sign"],
        trade["currency"],
    )


PRICERS: dict[str, tuple[PnLMethod, Pricer]] = {
    ProductType.GOVT_BOND.value: (PnLMethod.BOND_CLEAN_PRICE, _price_bond),
    ProductType.CORP_BOND.value: (PnLMethod.BOND_CLEAN_PRICE, _price_bond),
    ProductType.IRS.value: (PnLMethod.SWAP_DV01, _price_swap),
    ProductType.CDS.value: (PnLMethod.CDS_CS01, _price_cds),
    ProductType.FX_SPOT.value: (PnLMethod.FX_RATE_MOVE, _price_fx),
    ProductType.FX_FORWARD.value: (PnLMethod.FX_RATE_MOVE, _price_fx),
    ProductType.FX_NDF.value: (PnLMethod.FX_RATE_MOVE, _price_fx),
    ProductType.EQ_OPTION.value: (PnLMethod.EQUITY_CONTRACT, _price_equity),
    ProductType.EQ_FUTURE.value: (PnLMethod.EQUITY_CONTRACT, _price_equity),
}


def compute_pnl(data: Dataset, as_of: date = AS_OF_DATE, since: date | None = None) -> PnLResult:
    """Value every trade held on `as_of`.

    With `since` unset the reference is the level the trade was struck at, so
    the result is P&L since inception. With `since` set the reference is that
    day's close and the result is the move over the window -- except for trades
    struck inside it, which still measure from their own traded level.

    A settled FX trade is valued at its closing date rather than at `as_of`:
    the cash was exchanged, so its P&L is realised and stops moving with spot.

    Both dates are validated up front. Valuing the book on a day the desk never
    published would otherwise price the handful of trades that happen to close
    on an earlier date and silently report the total as the desk's P&L, and an
    inverted window would measure the market backwards and return a plausible
    number with the wrong sign.
    """
    _validate_window(data, as_of, since)

    as_of_ts = pd.Timestamp(as_of)
    issues: list[DataQualityIssue] = []

    held = data.trades[
        data.trades["trade_date"].notna() & (data.trades["trade_date"] <= as_of_ts)
    ].copy()
    closing = closing_dates(held)
    levels, inputs = _Levels(data), _Inputs(data)

    rows: list[dict] = []
    for idx, trade in held.iterrows():
        method, pricer = PRICERS[trade["product_type"]]

        # Realised positions stop marking on the day they closed.
        close = closing[idx]
        valuation_date = min(as_of_ts, close) if pd.notna(close) else as_of_ts

        reference, current, issue = _levels_for(trade, levels, valuation_date, since, close)
        if issue is not None:
            issues.append(issue)
            continue

        try:
            amount, currency = pricer(trade, current - reference, inputs)
        except LookupError as missing:
            issues.append(_missing_sensitivity(trade, str(missing)))
            continue

        rows.append(
            {
                "trade_id": trade["trade_id"],
                "book_id": trade["book_id"],
                "asset_class": trade["asset_class"],
                "product_type": trade["product_type"],
                "instrument_id": trade["instrument_id"],
                "currency": trade["currency"],
                "method": method.value,
                "valuation_date": valuation_date.date(),
                "reference_level": reference,
                "current_level": current,
                "pnl_ccy": amount,
                "pnl_currency": currency,
                "pnl_usd": data.fx.to_usd(amount, currency, valuation_date.date()),
            }
        )

    # Built against the model's own field list so that a run with nothing to
    # value still returns the full schema. A bare DataFrame([]) has no columns
    # at all, and every caller reading .trades["trade_id"] would raise on a
    # date the desk simply held no positions.
    priced = pd.DataFrame(rows, columns=list(TradePnL.model_fields))

    return PnLResult(trades=priced, issues=merge(issues))


def _validate_window(data: Dataset, as_of: date, since: date | None) -> None:
    """Refuse a valuation the extract cannot support, before pricing anything."""
    if since is not None and since > as_of:
        raise ValueError(f"since={since} is after as_of={as_of}; a P&L window cannot run backwards")

    available = data.business_days
    for label, day in (("as_of", as_of), ("since", since)):
        if day is None or pd.Timestamp(day) in available:
            continue
        raise ValueError(
            f"{label}={day} is not a day this extract prices. It covers "
            f"{available[0].date()} to {available[-1].date()}, business days only."
        )


def _levels_for(trade, levels, valuation_date, since, closing_date):
    """Resolve the reference and current level, or explain why we cannot."""
    current = levels.market(trade, valuation_date.date())
    if current is None:
        return None, None, _missing_quote(trade, valuation_date, "valuation")

    # A trade that closed on or before the window opened earned nothing inside
    # it: its P&L was realised earlier. Referencing the window's opening level
    # against a closing level that precedes it would measure the market
    # backwards and credit the desk with a move it never had.
    if since is not None and pd.notna(closing_date) and closing_date <= pd.Timestamp(since):
        return current, current, None

    if since is None or trade["trade_date"] > pd.Timestamp(since):
        return float(trade["trade_price"]), current, None

    reference = levels.market(trade, since)
    if reference is None:
        return None, None, _missing_quote(trade, pd.Timestamp(since), "reference")

    return reference, current, None


def _missing_quote(trade: pd.Series, on: pd.Timestamp, role: str) -> DataQualityIssue:
    return DataQualityIssue(
        code=IssueCode.MISSING_MARKET_DATA,
        severity=Severity.ERROR,
        entity_type="trade",
        entity_id=str(trade["trade_id"]),
        detail=(
            f"no {role} level for {trade['instrument_id']} on {on.date()}, "
            f"so the trade cannot be marked"
        ),
        treatment="Excluded from P&L rather than valued at a stale or assumed level.",
    )


def _missing_sensitivity(trade: pd.Series, metric: str) -> DataQualityIssue:
    return DataQualityIssue(
        code=IssueCode.MISSING_SENSITIVITY,
        severity=Severity.ERROR,
        entity_type="trade",
        entity_id=str(trade["trade_id"]),
        detail=f"{metric} missing from the risk file; {trade['product_type']} is priced from it",
        treatment="Excluded from P&L rather than assumed zero.",
    )
