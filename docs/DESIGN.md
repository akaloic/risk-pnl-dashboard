# Design

How the tool is put together, and the decisions behind it. The short version is
in the [README](../README.md); this is the argument.

---

## Architecture

```
loaders → dq → positions → { pnl → analytics, risk } → api
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
| `risk` | Aggregate sensitivities by book and metric, and split them along the curve. |
| `counterparty` | Rank the names the desk faces by what a default would cost. |
| `checks` / `reconciliation` | Market data quality; blotter against risk file. |
| `report` | Assemble every finding into one ordered report. |
| `api` | Thin FastAPI layer over the engines. |

### Design decisions

#### How the numbers are built


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



#### What the risk views answer


**Risk is reported along the curve, not just as a book total.** A book-level
DV01 says what a parallel shift is worth and nothing about where the position
sits, and it hides a curve trade completely — a long and a short of equal size
net to almost nothing while carrying real exposure to the shape. RATES-ASIA-01
is exactly that: a total of 6,442 USD that is actually short the front and the
belly and long the 5-10Y point. Buckets come from each trade's own
`maturity_date` rather than from parsing an instrument id, and their order is
carried as data — sorted as text, `10Y+` lands between `0-3M` and `1-3Y`.

**The front of the curve is split at three months, not at a year.** A single
0-1Y bucket held 17 trades maturing anywhere from 22 to 309 days out, and 16 of
those 17 fall inside 60 days. Splitting it says what the desk actually looks
like: **100% of the equity derivatives book and 100% of the FX book mature
within three months**, carrying 396k USD of the 444k loss, while the rates
position that shared the old bucket sits at 3-12M. Rows where most of the gross
exposure is near-term are marked `rolls off` on screen — measured gross rather
than net, because a front-end long against a far short cancels to zero and
still rolls off.

**Counterparty exposure is not notional.** A ten million dollar forward against
Citi is ten million of business and, on this extract, no credit risk at all: the
trade is marked against the desk, so the name owes nothing and a default costs
nothing. Exposure is the mark where it is positive and zero where it is not.
Netting instead would report a relationship the desk is losing on as costing
nothing to lose — Nomura nets to −149k and would still take 132k out of the desk
tomorrow. And the notional column has to be converted before it is compared:
summed as it stands, mixing JPY, KRW and USD, KB Securities is 61% of the book
and first by a distance; in USD it is 9.4% and sixth; by exposure it is 4.5%.
Three questions, three orderings, and only one of them is a credit limit.



#### How the screen reads


**A trade is not a position.** The P&L table sorts by size, so the two largest
lines in EQD-ASIA-01 were TRD-034 at −113k and TRD-039 at +103k — both Nikkei
September futures, one position netting to −10k. Read as separate rows, the
worst line on the desk looked eleven times worse than it was. Trades sharing an
instrument are now marked `leg` with the net beside them; on that book 8 of the
10 rows are legs of 6 positions.

**The positions table sorts by magnitude, not by value.** The question a desk
asks is "what is my biggest position", and a short of 5m matters exactly as
much as a long of 5m — sorting signed would bury every short behind every long,
however small. The sign is carried by colour instead. All nine columns sort and
the direction toggles: half a table being inert taught a user that sorting does
not work here, which is worse than not offering it.

**Weight is only assigned where the unit is common.** Every figure carrying the
same typographic weight meant a JTD of −14.8m and a CS01 of 4,500 looked
equally important and the eye had nothing to land on. Figures that dominate
their own set now read heavier — but only within a set in one unit: down the
P&L column of a trade table, or across one row of the curve grid where every
cell is the same metric at a different tenor. Down a *column* of the curve grid
would be a JTD against a CS01, and across a positions table would be yen
against dollars; in both the heaviest number on screen would be the one in the
smallest currency. A lone figure is never marked, since there is nothing for it
to be big against.

**The morning screen says what the risk tab knew.** A book card answered "this
book is down 143k" and not "and all of it expires within the quarter", which
was on another tab and therefore unread. Cards now carry `rolls off ≤3M` when
every risk metric on the book is near-term — on this extract, the equity
derivatives and FX books. Counted per metric rather than summed across them:
adding a book's Delta, DV01 and JTD to get "its near-term exposure" produces a
number dominated by whichever metric is quoted in the largest units.

**Accessibility is checked by a machine, because two careful readings were not
enough.** `aria-selected` on plain buttons is invalid — the attribute is only
allowed on a handful of roles — and it survived a deliberate accessibility pass
here before being found by hand. Two layers now run on every `npm test`:
oxlint's `jsx-a11y` rules read the source, and axe-core runs over what each of
the nine components actually renders, which is where a role with no container,
an `aria-controls` pointing at nothing, or a heading level that skips can only
be seen. Turning it on immediately found two more: the chart's book filter was
a combo box with no accessible name, and the summary cards jumped from `h1` to
`h3`. One test in that file asserts the check still *fails* on a known-bad
fragment — an assertion helper that quietly stops asserting passes every test
it is in, and reads as evidence.

---

## Endpoints

`GET /health` · `/positions` · `/pnl` · `/pnl/trades` · `/risk` ·
`/counterparty` · `/data-quality` · `/reconciliation`

All except `/health` accept `?as_of=YYYY-MM-DD` to replay any published
business day. A date the extract does not price returns **400** with the range
it covers, rather than a partial answer.

---

## Tests

```bash
source .venv/bin/activate && python -m pytest
```

```bash
cd frontend && npm test
```

189 backend tests and 124 on the front end, and they pass on a fresh clone
**with no `data/` directory at all**: the suite runs against hand-written
fixtures in `tests/fixtures/` that reproduce every quirk found in the real
extracts. That is deliberate — the real files are confidential and are not in
this repository.

They split in two. Seven pure modules — axis scaling, formatting, the series
aggregation, the curve pivot, the leg grouping, the sort order and the emphasis
rule — are tested without a DOM, because that is where a wrong answer is
silent: a mis-scaled axis, a mis-grouped total, a curve sorted
`0-3M, 10Y+, 1-3Y` and a hedged position read as two losing trades all draw a
screen that looks entirely normal.

All nine components are then rendered and driven, which is what stops a
correct function from being asked the wrong question. Those tests assert what
the screen has to say rather than how it is built: that a badge claiming a book
rolls off never appears on a book holding far-dated risk, that the two legs of
one instrument show their net, that a large short sorts alongside a large long
instead of below every long, that the panel never shows a finding without its
treatment, and that a failed request surfaces the backend's own explanation
rather than replacing it with a status code.
