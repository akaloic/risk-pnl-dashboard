"""The composition root: load the four extracts once, clean once.

Every consumer needs the same starting point -- a cleaned blotter, the quote
and risk frames, and an FX grid -- and assembling it inline was already
repeated in four places. Two things go wrong when that assembly is spread out.
The daily P&L replay values the book on each of the month's business days, so
re-reading and re-cleaning per date is both wasteful and, worse, re-detects
every anomaly once per date: the data quality report would show the same
duplicate trade twenty-four times over. And each caller would be free to
assemble the pipeline slightly differently, which is exactly how two screens
end up disagreeing about the same number.

The raw blotter is kept alongside the cleaned one so reconciliation can still
compare the tool's view against the file as delivered.

Not cached deliberately: the tests redirect RAD_DATA_DIR at runtime, and a
process-wide cache would serve them stale frames. The API layer holds a single
instance for the life of the process instead.
"""

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from app.dq import clean_trades
from app.fx import FxRates
from app.issues import DataQualityIssue, merge
from app.loaders import (
    load_fx_rates_raw,
    load_market_data_raw,
    load_risk_sensitivities_raw,
    load_trades_raw,
)


@dataclass(frozen=True)
class Dataset:
    """The four extracts, cleaned and ready to price.

    Treat the frames as read-only: they are shared by every engine, and a
    caller that mutates one changes what the next screen shows.
    """

    trades: pd.DataFrame
    raw_trades: pd.DataFrame
    quotes: pd.DataFrame
    risk: pd.DataFrame
    fx: FxRates
    issues: list[DataQualityIssue] = field(default_factory=list)

    @property
    def business_days(self) -> list[pd.Timestamp]:
        """Days the extract can be valued on, ascending.

        Taken from the intersection of the quote and FX grids: a day priced
        without a rate to convert it, or converted without a price, is not a
        day the book can be reported on.
        """
        quoted = set(self.quotes["date"].unique())
        return sorted(quoted & set(self.fx.dates))


def load_dataset(data_dir: Path | None = None) -> Dataset:
    """Load and clean the four extracts.

    `data_dir` overrides the configured location; leaving it unset resolves
    through RAD_DATA_DIR, then the repo's own data/ directory.
    """
    trades_path = data_dir / "trades.csv" if data_dir else None
    quotes_path = data_dir / "market_data.csv" if data_dir else None
    risk_path = data_dir / "risk_sensitivities.csv" if data_dir else None
    fx_path = data_dir / "fx_rates.csv" if data_dir else None

    raw_trades = load_trades_raw(trades_path)
    cleaned = clean_trades(raw_trades)

    return Dataset(
        trades=cleaned.trades,
        raw_trades=raw_trades,
        quotes=load_market_data_raw(quotes_path),
        risk=load_risk_sensitivities_raw(risk_path),
        fx=FxRates(load_fx_rates_raw(fx_path)),
        issues=merge(cleaned.issues),
    )
