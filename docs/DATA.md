# What the extracts turned out to contain

Every finding below is detected at runtime and shown in the Data quality panel
with the treatment applied — none of it is hard-coded. The short version is in
the [README](../README.md).

---

## What was found in the data

**32 findings** as of 2026-08-05: 5 errors, 23 warnings, 4 benign. The `code`
column is the name the panel shows on screen and the tests assert on.

| # | What | Code | Where | Treatment |
|---|---|---|---|---|
| 1 | Exact duplicate blotter row | `DUPLICATE_TRADE_ROW` | TRD-015 | Dropped, first kept. Keeping it doubles the trade's CREDIT P&L while the risk file carries one set of sensitivities — the two would stop reconciling. |
| 2 | `trade_date` as MM/DD/YYYY | `MALFORMED_TRADE_DATE` | TRD-023, TRD-034 | Repaired, but only because the alternative reading is impossible (no 28th month). An ambiguous date is left null and escalated. Each repair is cross-checked against `settle_date`. |
| 3 | Side encoded twice: quantity −100 **and** SELL | `NEGATIVE_QUANTITY_WITH_DIRECTION` | TRD-039 | Quantity taken as a magnitude; direction carries the sign. Taken literally it multiplies out to a long and flips the P&L. |
| 4 | No contract multiplier anywhere in the extracts | — | NKY, HSI, KOSPI200 | Recovered from the risk file: `Delta_USD = qty × multiplier × price / fx` inverts to 1,000 and 250. Without them the equity P&L is out by up to 1,000×. HSI has no future to invert, so 50 is the exchange spec, corroborated but not derived. |
| 5 | FX absent from `market_data.csv` | — | all FX | Valued from `fx_rates.csv` alone; exposure derived from the blotter and cross-checked against `Delta_USD`. |
| 6 | Settled FX spots still marked LIVE | `SETTLED_TRADE_MARKED_LIVE`<br>`SETTLED_TRADE_CARRIES_RISK` | TRD-021/022/024 | Classified SETTLED and excluded from open risk. The risk file still publishes **19.4m USD** of delta for them, against 18.6m genuinely open. |
| 7 | Quote timestamped a day before its snapshot | `STALE_QUOTE` | CDB-3.4-2028 @ 08-05 | Used as published — it is the only price for that day — and flagged so the P&L it feeds can be challenged. |
| 8 | Implausible durations | `IMPLAUSIBLE_DURATION` | 4 swaps + 4 bonds | The four swaps carry 0.9y regardless of tenor. Worse, four bonds carry a duration **longer than their remaining life** — TRD-010 shows 7.82y on a bond maturing in ten months. Quarantined: duration feeds no number. |
| 9 | Risk metric naming | — | all | Normalised onto the glossary spelling on ingest, so one sensitivity cannot split across two buckets. |
| 10 | Equity notional booked as 0 | — | all EQD | Sized on contracts × multiplier; a notional-driven valuation reports the book flat. |
| 11 | `value_usd` consistency | `VALUE_USD_MISMATCH` | 24 rows | All reconcile to the cent — checked at the date each row was struck, and only for rows denominated in a currency. Duration is in years; converting a tenor would leave the check permanently red. |
| 12 | Instruments quoted but never traded | `QUOTE_WITHOUT_POSITION` | 4 instruments | Ignored cleanly: the position is zero. |

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

- **FX forwards and NDFs are marked on spot.** `fx_rates.csv` carries one
  `spot_rate` per pair per day and nothing else — no forward points, no tenor
  curve — so the rate differential between the two legs cannot be marked and
  is absent from the figure. Six term trades are valued this way and they
  carry **267k USD, about 60% of the desk total**, which is why this is the
  first limitation listed rather than a footnote. The error is the *change* in
  the forward points over the holding period, not the points themselves: both
  the reference and the current level are spot, so carry that does not move
  cancels. Closing it needs a forward curve the extract does not contain.
- No database, no auth, no Docker. Two commands to run is the point.
- Pricing iterates row-wise rather than vectorised. At 40 trades over 24 days
  the cost is invisible, and five readable pricing functions are worth more
  here than a faster one nobody can check.
- The P&L is a mark-to-market against traded and published levels. There is no
  accrual, no funding, and no intraday.
- Option risk is taken from the pricing library as published; nothing is
  re-priced from a volatility surface.
