# Risk & P&L — Asia cross-asset desk

A working risk and P&L tool for four books out of Asia — rates, credit, FX and
equity derivatives — built on extracts from the desk's source systems.
Reporting currency **USD**, as of **2026-08-05**, with the whole month
replayable day by day.

```mermaid
flowchart LR
  CSV["4 CSV extracts"] --> ingest["loaders + dq"] --> positions
  positions --> pnl --> analytics --> api["FastAPI"] --> ui["React screen"]
  positions --> risk --> api
  positions --> counterparty --> api
```

Dependencies run one way only. Every engine is testable without starting a web
server, which is why the numbers can be checked without the screen.

## Run it

**Python 3.11–3.14, Node 18+.** Two terminals.

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r backend/requirements.txt
```

```bash
cd frontend && npm install
```

**With the extracts** — drop `trades.csv`, `market_data.csv`,
`risk_sensitivities.csv` and `fx_rates.csv` into `data/`. They are gitignored
and never committed.

```bash
PYTHONPATH=backend uvicorn app.main:app --reload
```

**Or on the demo desk.** `demo-data/` holds an invented one, which exists so
the screenshots below can show a working screen without publishing a single
real figure. It also means the app starts on a fresh clone:

```bash
RAD_DATA_DIR=demo-data PYTHONPATH=backend uvicorn app.main:app --reload
```

Either way, start the screen with `cd frontend && npm run dev` and open
<http://localhost:5173>. API docs at <http://localhost:8000/docs>.

**Tests:** `python -m pytest` and `cd frontend && npm test` — 189 + 124, and
they pass on a fresh clone **with no `data/` directory at all**, against
hand-written fixtures that reproduce the real quirks.

## What it looks like

All of them are the demo desk: invented books, invented counterparties, not one
figure derived from the extracts. That is the point of `demo-data/` — the real
screen names the counterparties the desk faces and what each owes, which is not
something to commit. Regenerate with `scripts/make_demo_data.py` and
`scripts/take_screenshots.py`.

**Desk summary** — where each book stands, what moved overnight, and whether it
is a position we still have. `rolls off ≤3M` marks a book whose every risk
metric matures inside the quarter.

![Desk summary](docs/screenshots/01-desk-summary.png)

**Drill-down** — the trades behind a figure, biggest first, with the levels
each was computed from. `leg` marks lines that share an
instrument and are one position: read separately, DEM-021 looks like a 89k
loss, and it is half of a position that made 14k.

![P&L by trade](docs/screenshots/02-trade-detail.png)

**Risk** — what the desk is exposed to and where on the curve it sits. Settled
exposure stays visible beside open, and `curve` marks a row holding exposure on
both sides of zero.

![Risk](docs/screenshots/04-risk.png)

**Counterparty** — who the desk faces, ranked by what a default would cost
rather than by notional, which is a different ordering.

![Counterparty exposure](docs/screenshots/05-counterparty.png)

**Data quality** — what was wrong with the extracts, and what the tool did
about each of it.

![Data quality](docs/screenshots/06-data-quality.png)

And [Positions](docs/screenshots/03-positions.png): what is held, netted by
book and instrument, with what has settled still on show.

## Nothing is repaired silently

```mermaid
flowchart LR
  D["defect found"] --> Q{"repairable without<br/>guessing?"}
  Q -->|yes| R["repair, record the treatment"]
  Q -->|no| E["escalate untreated, record why"]
  R --> P["DQ panel"]
  E --> P
```

**32 findings** on this extract — 5 errors, 23 warnings, 4 benign — each shown
with what the tool did about it. A figure a trader disputes at 07:30 is only
useful if we can say exactly what changed underneath it.

## The three things the data hid

**No contract multiplier exists anywhere in the extracts.** Equity trades book
a notional of 0 and a quantity in contracts. Left at 1, the Nikkei book is
wrong by a factor of 1,000 and still looks entirely plausible on screen. The
values were recovered by inverting the risk file's own identity, cross-checked
on independent trades — and HSI, which has no future to invert, is labelled
*corroborated, not derived*.

**A naive settlement rule empties the book.** 34 of 40 trades have a settlement
date in the past. Settlement ends an FX spot and *starts* a bond. And the NDFs
carry a spot-leg `settle_date` while running to maturity a month later.

**Notional is not exposure, and it is not even comparable.** Summed raw across
JPY, KRW and USD, one counterparty is 61% of the book and first by a distance;
in USD it is 9.4% and sixth; by what a default would actually cost, 4.5%.

## What it does not do

FX forwards and NDFs are marked on spot: `fx_rates.csv` has no forward points,
so the rate differential is absent from **267k USD, about 60% of the desk
total**. Stated here rather than buried, because it is the largest
approximation in the tool.

---

**Detail:** [Design decisions and architecture](docs/DESIGN.md) ·
[What the extracts turned out to contain](docs/DATA.md) — the 32 findings in
full, four things found beyond the brief, three questions left open for the
desk.
