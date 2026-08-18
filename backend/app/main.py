"""The REST layer.

Thin on purpose: every route resolves the dataset, calls one engine, and hands
back typed rows. All of the judgement lives in the modules below it, which is
what lets the numbers be tested without a web server.

The dataset is loaded once for the life of the process. Reading and cleaning
four extracts on every request would be wasteful, but the real reason is that
the data quality report would then be recomputed per request against frames
that could differ if the files changed underneath a running desk.
"""

from datetime import date
from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from app.analytics import BookSummary, DailyPnL, daily_pnl_series, desk_summary
from app.config import AS_OF_DATE, REPORTING_CCY
from app.dataset import Dataset, load_dataset
from app.issues import DataQualityIssue
from app.loaders import to_records
from app.pnl import TradePnL, compute_pnl
from app.positions import Position, build_positions
from app.reconciliation import coverage_summary, reconcile
from app.report import full_quality_report, severity_counts
from app.risk import RiskAggregate, aggregate_risk, non_additive_metrics

app = FastAPI(
    title="Risk & P&L -- Asia cross-asset desk",
    description=(
        "Positions, P&L and risk for the rates, credit, FX and equity derivatives "
        "books, with every data quality treatment applied to get there on show."
    ),
    version="0.1.0",
)

# The Vite dev server runs on another port, so the browser treats the API as a
# different origin. Development hosts only -- this prototype is not deployed.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@lru_cache(maxsize=1)
def _dataset() -> Dataset:
    return load_dataset()


def get_dataset() -> Dataset:
    """Dependency handing every route the same loaded, cleaned dataset."""
    return _dataset()


def reset_dataset_cache() -> None:
    """Drop the cached dataset. Used by the tests, which swap the data directory."""
    _dataset.cache_clear()


def valuation_date(
    as_of: date | None = Query(
        None,
        alias="as_of",
        description="Business day to value on. Defaults to the reference as-of date.",
    ),
) -> date:
    """The one date every endpoint reads, named the same as the engines' own.

    The alias is `as_of` rather than `date` so that the 400 an engine raises --
    "as_of=2030-01-01 is not a day this extract prices" -- names the parameter
    the caller actually sent. FastAPI ignores query parameters it does not
    know, so a caller who retries with the name the error suggested would
    otherwise get the default date back and no indication anything was wrong.
    Every response echoes `as_of`, which is the check that this landed.
    """
    return as_of or AS_OF_DATE


class Health(BaseModel):
    status: str
    as_of: date
    reporting_currency: str
    trades: int
    business_days: int
    first_business_day: date
    last_business_day: date


class PnLResponse(BaseModel):
    """What the desk summary needs in one call: the cards and the chart."""

    as_of: date
    reporting_currency: str
    total_day_usd: float
    total_inception_usd: float
    by_book: list[BookSummary]
    series: list[DailyPnL]


class RiskResponse(BaseModel):
    as_of: date
    by_book: list[RiskAggregate]
    per_trade_tenors: list[dict]


class DataQualityResponse(BaseModel):
    as_of: date
    counts: dict[str, int]
    issues: list[DataQualityIssue]


class ReconciliationResponse(BaseModel):
    as_of: date
    coverage: list[dict]
    issues: list[DataQualityIssue]


def _guard(call):
    """Turn an engine's refusal into a 400 rather than a 500.

    The engines raise ValueError when asked to value a day the extract does not
    price, and that message names the range they do cover -- worth passing on
    to the caller rather than swallowing into a server error.
    """
    try:
        return call()
    except ValueError as invalid:
        raise HTTPException(status_code=400, detail=str(invalid)) from invalid


@app.get("/health", response_model=Health, tags=["service"])
def health(data: Dataset = Depends(get_dataset)) -> Health:
    days = data.business_days
    return Health(
        status="ok",
        as_of=AS_OF_DATE,
        reporting_currency=REPORTING_CCY,
        trades=len(data.trades),
        business_days=len(days),
        first_business_day=days[0].date(),
        last_business_day=days[-1].date(),
    )


@app.get("/positions", response_model=list[Position], tags=["desk"])
def positions(
    as_of: date = Depends(valuation_date),
    data: Dataset = Depends(get_dataset),
) -> list[Position]:
    book = _guard(lambda: build_positions(data.trades, as_of=as_of))
    return [Position.model_validate(row) for row in to_records(book.positions)]


@app.get("/pnl", response_model=PnLResponse, tags=["desk"])
def pnl(
    as_of: date = Depends(valuation_date),
    data: Dataset = Depends(get_dataset),
) -> PnLResponse:
    # The month is replayed once and reused: the cards and the chart are the
    # same figures, and building the series twice doubled this route's work.
    series, _ = _guard(lambda: daily_pnl_series(data, as_of=as_of))
    summary = _guard(lambda: desk_summary(data, as_of=as_of, series=series))

    return PnLResponse(
        as_of=as_of,
        reporting_currency=REPORTING_CCY,
        total_day_usd=float(summary["day_usd"].sum()),
        total_inception_usd=float(summary["inception_usd"].sum()),
        by_book=[BookSummary.model_validate(row) for row in to_records(summary)],
        series=[DailyPnL.model_validate(row) for row in to_records(series)],
    )


@app.get("/pnl/trades", response_model=list[TradePnL], tags=["desk"])
def pnl_by_trade(
    as_of: date = Depends(valuation_date),
    data: Dataset = Depends(get_dataset),
) -> list[TradePnL]:
    """Per-trade detail behind the book totals, so a figure can be taken apart."""
    priced = _guard(lambda: compute_pnl(data, as_of=as_of))
    return [TradePnL.model_validate(row) for row in to_records(priced.trades)]


@app.get("/risk", response_model=RiskResponse, tags=["desk"])
def risk(
    as_of: date = Depends(valuation_date),
    data: Dataset = Depends(get_dataset),
) -> RiskResponse:
    grid = _guard(lambda: aggregate_risk(data, as_of=as_of))
    return RiskResponse(
        as_of=as_of,
        by_book=[RiskAggregate.model_validate(row) for row in to_records(grid)],
        per_trade_tenors=to_records(non_additive_metrics(data)),
    )


@app.get("/data-quality", response_model=DataQualityResponse, tags=["quality"])
def data_quality(
    as_of: date = Depends(valuation_date),
    data: Dataset = Depends(get_dataset),
) -> DataQualityResponse:
    issues = _guard(lambda: full_quality_report(data, as_of=as_of))
    return DataQualityResponse(as_of=as_of, counts=severity_counts(issues), issues=issues)


@app.get("/reconciliation", response_model=ReconciliationResponse, tags=["quality"])
def reconciliation(
    as_of: date = Depends(valuation_date),
    data: Dataset = Depends(get_dataset),
) -> ReconciliationResponse:
    issues = _guard(lambda: reconcile(data, as_of=as_of))
    return ReconciliationResponse(
        as_of=as_of,
        coverage=to_records(coverage_summary(data)),
        issues=issues,
    )
