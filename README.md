# Risk & P&L — Asia cross-asset desk

A prototype risk and P&L tool for four books out of Asia — rates, credit, FX
and equity derivatives — built on the extracts from the desk's source systems.

Reporting currency is **USD**. Reference as-of date is **2026-08-05**, and the
whole month from 2026-07-03 can be replayed day by day.

---

## Running it

**Requirements:** Python 3.11–3.13 and Node 18+.

> Python 3.14 does not work: pydantic 2.10 has no wheel for it yet and falls
> back to a Rust build that fails.

Drop the four extracts into `data/` — they are gitignored and never committed:

```
data/trades.csv
data/market_data.csv
data/risk_sensitivities.csv
data/fx_rates.csv
```

**Two commands**, each in its own terminal:

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r backend/requirements.txt && PYTHONPATH=backend uvicorn app.main:app --reload
```

```bash
cd frontend && npm install && npm run dev
```

Then open <http://localhost:5173>. The API is on <http://localhost:8000>, with
interactive docs at <http://localhost:8000/docs>.

### Tests

```bash
source .venv/bin/activate && python -m pytest
```

158 tests, and they pass on a fresh clone **with no `data/` directory at all**:
the suite runs against hand-written fixtures in `tests/fixtures/` that
reproduce every quirk found in the real extracts. That is deliberate — the real
files are confidential and are not in this repository.

---

## What it does

| View | Answers |
|---|---|
| **Desk summary** | Where does each book stand, and what moved overnight? Daily P&L chart over the month. |
| **Positions** | What do we actually hold, netted by book and instrument, and what has settled? |
| **Risk** | What are we exposed to, per book and metric — and how much of that exposure is real? |
| **Data quality** | What was wrong with the data, and what did the tool do about it? |

### Endpoints

`GET /health` · `/positions` · `/pnl` · `/pnl/trades` · `/risk` ·
`/data-quality` · `/reconciliation`

All except `/health` accept `?date=YYYY-MM-DD` to replay any published business
day. A date the extract does not price returns **400** with the range it covers,
rather than a partial answer.

---

## Architecture

```
loaders → dq → positions → pnl → analytics → api
config · models · issues · contracts · fx      (leaf helpers)
```

Dependencies run one way only; there are no cycles. Each layer is testable
without the one above it, which is why the numbers can be verified without
starting a web server.

| Module | Responsibility |
|---|---|
| `loaders` | Read the CSVs, coerce dtypes, reject undocumented values. No repairs. |
| `dq` | Clean the blotter, recording every treatment applied. |
| `positions` | Net by book and instrument; decide what has settled. |
| `pnl` | Mark to market, one pricing method per product class. |
| `analytics` | Replay the month; summarise per book. |
| `checks` / `reconciliation` | Market data quality; blotter against risk file. |
| `report` | Assemble every finding into one ordered report. |
| `api` | Thin FastAPI layer over the engines. |

### Design decisions

**Loaders never repair anything.** They validate types and domains and stop
there. Every fix lives in the data-quality layer with a recorded treatment, so
the raw frame stays available to reconcile against the source system, and no
correction is ever buried inside a `read_csv` call.

**Each engine returns `(result, issues)`.** One shared vocabulary of issue
codes means the data quality panel, the tests and this README all name the same
finding the same way, and a new check anywhere shows up in the report for free.

**The dataset is assembled once.** The daily replay values the book on 24
business days; re-cleaning per day would report the same duplicate trade 24
times over.

**FX conversion is its own module.** The extract mixes both quoting conventions
— USD is the base of USDJPY but the quote of EURUSD — and getting one backwards
raises nothing, warns about nothing, and produces a plausible number that is
wrong by a factor of 150. The direction is derived from the file's own
`base_ccy`/`quote_ccy` columns and pinned by tests in both directions.

**Pricing is a registry, not a conditional.** Five methods, five short
functions behind a lookup on product type. Adding a product means adding a
function.

**Nothing is valued at an assumed level.** A missing price or sensitivity
excludes the trade and raises an error rather than defaulting to zero or
carrying yesterday's number forward.

---

## What was found in the data

Every item below is detected at runtime and shown in the Data quality panel
with the treatment applied. **32 findings** as of 2026-08-05: 5 errors, 23
warnings, 4 benign.

| # | What | Where | Treatment |
|---|---|---|---|
| 1 | Exact duplicate blotter row | TRD-015 | Dropped, first kept. Keeping it doubles the trade's CREDIT P&L while the risk file carries one set of sensitivities — the two would stop reconciling. |
| 2 | `trade_date` as MM/DD/YYYY | TRD-023, TRD-034 | Repaired, but only because the alternative reading is impossible (no 28th month). An ambiguous date is left null and escalated. Each repair is cross-checked against `settle_date`. |
| 3 | Side encoded twice: quantity −100 **and** SELL | TRD-039 | Quantity taken as a magnitude; direction carries the sign. Taken literally it multiplies out to a long and flips the P&L. |
| 4 | No contract multiplier anywhere in the extracts | NKY, HSI, KOSPI200 | Recovered from the risk file: `Delta_USD = qty × multiplier × price / fx` inverts to 1,000 and 250. Without them the equity P&L is out by up to 1,000×. HSI has no future to invert, so 50 is the exchange spec, corroborated but not derived. |
| 5 | FX absent from `market_data.csv` | all FX | Valued from `fx_rates.csv` alone; exposure derived from the blotter and cross-checked against `Delta_USD`. |
| 6 | Settled FX spots still marked LIVE | TRD-021/022/024 | Classified SETTLED and excluded from open risk. The risk file still publishes **19.4m USD** of delta for them, against 18.6m genuinely open. |
| 7 | Quote timestamped a day before its snapshot | CDB-3.4-2028 @ 08-05 | Used as published — it is the only price for that day — and flagged so the P&L it feeds can be challenged. |
| 8 | Implausible durations | 4 swaps + 4 bonds | The four swaps carry 0.9y regardless of tenor. Worse, four bonds carry a duration **longer than their remaining life** — TRD-010 shows 7.82y on a bond maturing in ten months. Quarantined: duration feeds no number. |
| 9 | Risk metric naming | all | Normalised onto the glossary spelling on ingest, so one sensitivity cannot split across two buckets. |
| 10 | Equity notional booked as 0 | all EQD | Sized on contracts × multiplier; a notional-driven valuation reports the book flat. |
| 11 | `value_usd` consistency | 24 rows | All reconcile to the cent — checked at the date each row was struck, and only for rows denominated in a currency. Duration is in years; converting a tenor would leave the check permanently red. |
| 12 | Instruments quoted but never traded | 4 instruments | Ignored cleanly: the position is zero. |

### Found beyond the brief

- **NDF settlement convention.** The two NDFs carry `settle_date` = trade + 2
  business days — the spot leg — while running to maturity a month later.
  Closing FX on `settle_date` would have retired both and dropped 10.0m and
  −7.0m USD of live delta. Spot closes on `settle_date`, forwards and NDFs on
  `maturity_date`.
- **A position that cannot be marked.** TRD-011 holds 5m USD of Hongkong Land
  2029, which appears nowhere in `market_data.csv`. The mirror image of the
  harmless orphan quotes, and unlike them it means a book is incomplete.
- **Price and yield are not derived from one another.** Five bond series imply
  *negative* durations from their own price and yield moves. Bonds are
  therefore valued on clean price alone, per the desk's method, and the yield
  column is never used to verify P&L.
- **The risk file was priced off a different snapshot.** Its implied index
  levels (37,920.00 and 358.90) appear nowhere in the market data, whose quotes
  all carry four decimals of noise. On the KOSPI the gap is 4.5%, so equity
  delta and equity P&L cannot be expected to tie out exactly.

---

## Open questions for the desk

**TRD-027** is an FX spot with no `settle_date` whose maturity has passed. The
evidence says it settled; the documented rule keys on `settle_date` and cannot
confirm it. It is left **open** and escalated: carrying it open overstates open
FX delta by 12.0m USD, and retiring it on inference understates it by the same.
That is a decision for the desk, not for a loader.

**The daily P&L convention.** Market moves telescope in the currency they occur
in, but not once each day is converted at its own rate. The series therefore
reports the change in the mark, which is what a USD-reporting desk is
accountable for and keeps the chart and the summary card consistent. Summing
daily conversions instead would give the trading move excluding revaluation of
prior P&L — a different, equally valid figure, and about 2,200 USD apart on the
equity book.

**KOSPI 200 multiplier.** Every figure here is consistent with 250 KRW/point
and none with the KRX's actual 250,000. The data wins for this extract, but the
value must be rechecked before it is used against real KOSPI risk.

---

## Known limitations

Deliberate, given this is a prototype:

- No database, no auth, no Docker. Two commands to run is the point.
- Pricing iterates row-wise rather than vectorised. At 40 trades over 24 days
  the cost is invisible, and five readable pricing functions are worth more
  here than a faster one nobody can check.
- The P&L is a mark-to-market against traded and published levels. There is no
  accrual, no funding, and no intraday.
- Option risk is taken from the pricing library as published; nothing is
  re-priced from a volatility surface.
