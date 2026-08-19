"""Generate a synthetic desk, so the screenshots can show one.

The README needs pictures -- a reader decides whether to run any of this in
about ten seconds -- and a screenshot of the real screen names the
counterparties the desk faces and what each of them owes. Those files are
confidential, and a figure derived from them is no more publishable than the
file itself. So the screens in the README are drawn from a desk that does not
exist: four books, twenty-five trades across the five product classes, a month
of business days, and the same column layout the extracts use.

Starting on a fresh clone falls out of it, which is worth having but is not why
this exists. Anyone reviewing this already has the extracts.

It is deliberately not the test fixtures. Those are ten hand-written rows built
to pin edge cases, and a screen drawn from them shows none of what the tool is
for. This set is sized and structured so the views have something to say: a
rates book positioned across the curve rather than at one point, two legs of one
future in the equity book, an FX book that rolls off inside the quarter, and a
counterparty whose notional and whose credit exposure rank differently.

Deterministic: a fixed seed, so regenerating produces the same desk and the
screenshots in the README stay true.

    python scripts/make_demo_data.py        # writes demo-data/
    RAD_DATA_DIR=demo-data uvicorn app.main:app
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 20260805
START = date(2026, 7, 3)
AS_OF = date(2026, 8, 5)
OUT = Path(__file__).resolve().parents[1] / "demo-data"

BOOKS = ["RATES-DEMO-01", "CREDIT-DEMO-01", "FX-DEMO-01", "EQD-DEMO-01"]
COUNTERPARTIES = [
    ("CPTY-D1", "Northbank Securities"),
    ("CPTY-D2", "Harbour Capital"),
    ("CPTY-D3", "Meridian Bank"),
    ("CPTY-D4", "Calder & Co"),
    ("CPTY-D5", "Solstice Partners"),
]


def business_days(start: date, end: date) -> list[date]:
    days, day = [], start
    while day <= end:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    return days


DAYS = business_days(START, AS_OF)

# --- the instruments the demo desk trades -------------------------------------

# (id, description, asset class, price type, level on the first day)
INSTRUMENTS = [
    # Rates: spread along the curve so the tenor view has a shape to show.
    ("JPY-IRS-2Y", "JPY IRS 2Y", "RATES", "PAR_RATE", 0.42),
    ("JPY-IRS-5Y", "JPY IRS 5Y", "RATES", "PAR_RATE", 0.88),
    ("JPY-IRS-10Y", "JPY IRS 10Y", "RATES", "PAR_RATE", 1.34),
    ("AUD-IRS-7Y", "AUD IRS 7Y", "RATES", "PAR_RATE", 3.91),
    ("JGB-0.4-2031", "JGB 0.4% 2031", "RATES", "CLEAN", 99.21),
    ("JGB-1.2-2041", "JGB 1.2% 2041", "RATES", "CLEAN", 96.44),
    ("ACGB-3.0-2033", "ACGB 3.0% 2033", "RATES", "CLEAN", 97.88),
    # Credit
    ("ORION-2.6-2029", "Orion Holdings 2.6% 2029", "CREDIT", "CLEAN", 98.15),
    ("VERTEX-3.1-2028", "Vertex Industries 3.1% 2028", "CREDIT", "CLEAN", 100.42),
    ("KESTREL-4.0-2030", "Kestrel Energy 4.0% 2030", "CREDIT", "CLEAN", 95.70),
    ("CDS-ORION-5Y", "CDS Orion Holdings 5Y", "CREDIT", "SPREAD", 88.0),
    ("CDS-VERTEX-5Y", "CDS Vertex Industries 5Y", "CREDIT", "SPREAD", 141.0),
    # Equity: an index, a future and two options on it.
    # NKY is a listed contract, not confidential -- and using it means the demo
    # exercises the real multiplier lookup rather than a stub. The trades on it
    # are invented, which is the part that matters.
    ("NKY-INDEX", "Nikkei 225 Index", "EQUITY", "LAST", 38_140.0),
    ("NKY-FUT-2026-12", "Nikkei 225 Future Dec26", "EQUITY", "LAST", 38_205.0),
    ("NKY-CALL-39000-2026-12", "Nikkei 225 Call 39000 Dec26", "EQUITY", "LAST", 612.0),
    ("NKY-PUT-37000-2026-12", "Nikkei 225 Put 37000 Dec26", "EQUITY", "LAST", 588.0),
]

FX_PAIRS = [
    ("USDJPY", "USD", "JPY", 149.10),
    ("USDSGD", "USD", "SGD", 1.3412),
    ("EURUSD", "EUR", "USD", 1.0871),
    ("AUDUSD", "AUD", "USD", 0.6633),
]

# Daily drift and volatility per price type, chosen so a month of moves is
# visible on a chart without any day looking like a market event.
WALK = {
    "PAR_RATE": (0.004, 0.010),
    "CLEAN": (-0.02, 0.09),
    "SPREAD": (0.25, 1.4),
    "LAST": (6.0, 48.0),
}


def walk(rng: random.Random, start: float, kind: str, n: int) -> list[float]:
    drift, vol = WALK[kind]
    out, level = [], start
    for _ in range(n):
        out.append(round(level, 4))
        level += rng.gauss(drift, vol)
    return out


# --- the blotter --------------------------------------------------------------

# (id, book, product, instrument, ccy, notional, qty, price, direction, maturity)
# Sized so each view has something to show rather than one flat number: the
# rates book sits at four points on the curve, the equity book holds both legs
# of one future, and the FX book matures inside the quarter.
TRADES = [
    # RATES -- long the belly, short the front and the long end.
    ("DEM-001", 0, "IRS", "JPY-IRS-2Y", "JPY", 4_000_000_000, 1, 0.40, "PAY", "2028-07-06"),
    ("DEM-002", 0, "IRS", "JPY-IRS-5Y", "JPY", 6_000_000_000, 1, 0.85, "RECEIVE", "2031-07-08"),
    ("DEM-003", 0, "IRS", "JPY-IRS-10Y", "JPY", 3_000_000_000, 1, 1.30, "RECEIVE", "2036-07-10"),
    ("DEM-004", 0, "IRS", "AUD-IRS-7Y", "AUD", 200_000_000, 1, 3.88, "PAY", "2033-07-14"),
    (
        "DEM-005",
        0,
        "GOVT_BOND",
        "JGB-0.4-2031",
        "JPY",
        2_500_000_000,
        25_000,
        99.10,
        "BUY",
        "2031-03-20",
    ),
    (
        "DEM-006",
        0,
        "GOVT_BOND",
        "JGB-1.2-2041",
        "JPY",
        1_200_000_000,
        12_000,
        96.30,
        "BUY",
        "2041-09-20",
    ),
    (
        "DEM-007",
        0,
        "GOVT_BOND",
        "ACGB-3.0-2033",
        "AUD",
        90_000_000,
        900,
        97.60,
        "BUY",
        "2033-04-21",
    ),
    (
        "DEM-008",
        0,
        "GOVT_BOND",
        "JGB-0.4-2031",
        "JPY",
        800_000_000,
        8_000,
        99.35,
        "SELL",
        "2031-03-20",
    ),
    # CREDIT
    (
        "DEM-009",
        1,
        "CORP_BOND",
        "ORION-2.6-2029",
        "USD",
        8_000_000,
        8_000,
        98.00,
        "BUY",
        "2029-05-15",
    ),
    (
        "DEM-010",
        1,
        "CORP_BOND",
        "VERTEX-3.1-2028",
        "USD",
        6_000_000,
        6_000,
        100.30,
        "BUY",
        "2028-11-30",
    ),
    (
        "DEM-011",
        1,
        "CORP_BOND",
        "KESTREL-4.0-2030",
        "SGD",
        9_000_000,
        9_000,
        95.40,
        "BUY",
        "2030-02-28",
    ),
    (
        "DEM-012",
        1,
        "CORP_BOND",
        "ORION-2.6-2029",
        "USD",
        3_000_000,
        3_000,
        98.40,
        "SELL",
        "2029-05-15",
    ),
    ("DEM-013", 1, "CDS", "CDS-ORION-5Y", "USD", 10_000_000, 1, 85.0, "BUY", "2031-06-20"),
    ("DEM-014", 1, "CDS", "CDS-VERTEX-5Y", "USD", 5_000_000, 1, 145.0, "SELL", "2031-06-20"),
    # FX -- the whole book rolls off inside the quarter.
    ("DEM-015", 2, "FX_SPOT", "USDJPY", "USD", 12_000_000, 1, 148.90, "BUY", "2026-08-07"),
    ("DEM-016", 2, "FX_FORWARD", "USDJPY", "USD", 9_000_000, 1, 149.40, "SELL", "2026-09-30"),
    ("DEM-017", 2, "FX_FORWARD", "USDSGD", "USD", 7_000_000, 1, 1.3455, "BUY", "2026-09-15"),
    ("DEM-018", 2, "FX_NDF", "USDJPY", "USD", 5_000_000, 1, 149.75, "BUY", "2026-10-02"),
    ("DEM-019", 2, "FX_SPOT", "EURUSD", "EUR", 4_000_000, 1, 1.0860, "BUY", "2026-08-07"),
    ("DEM-020", 2, "FX_FORWARD", "AUDUSD", "AUD", 6_000_000, 1, 0.6650, "SELL", "2026-09-18"),
    # EQD -- two legs of one future, plus options on the same underlying.
    ("DEM-021", 3, "EQ_FUTURE", "NKY-FUT-2026-12", "JPY", 0, 150, 38_150.0, "BUY", "2026-12-11"),
    ("DEM-022", 3, "EQ_FUTURE", "NKY-FUT-2026-12", "JPY", 0, 60, 38_320.0, "SELL", "2026-12-11"),
    ("DEM-023", 3, "EQ_OPTION", "NKY-CALL-39000-2026-12", "JPY", 0, 80, 640.0, "BUY", "2026-12-11"),
    ("DEM-024", 3, "EQ_OPTION", "NKY-PUT-37000-2026-12", "JPY", 0, 50, 560.0, "BUY", "2026-12-11"),
    (
        "DEM-025",
        3,
        "EQ_OPTION",
        "NKY-CALL-39000-2026-12",
        "JPY",
        0,
        30,
        655.0,
        "SELL",
        "2026-12-11",
    ),
]


def write(name: str, header: list[str], rows: list[list]) -> None:
    OUT.mkdir(exist_ok=True)
    with (OUT / f"{name}.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    print(f"  demo-data/{name}.csv  {len(rows)} rows")


def main() -> None:
    rng = random.Random(SEED)

    # --- market data: every instrument on every business day ------------------
    levels: dict[str, list[float]] = {}
    md_rows = []
    for iid, desc, asset, ptype, start in INSTRUMENTS:
        levels[iid] = walk(rng, start, ptype, len(DAYS))
        for day, level in zip(DAYS, levels[iid], strict=True):
            spread = level * (0.0002 if ptype != "SPREAD" else 0.01)
            bid, ask = round(level - spread, 4), round(level + spread, 4)
            # yield_pct only for bonds, spread_bps only for CDS -- the columns
            # the extracts leave empty are left empty here too.
            md_rows.append(
                [
                    day.isoformat(),
                    iid,
                    desc,
                    asset,
                    level if ptype == "LAST" else "",
                    level
                    if ptype == "PAR_RATE"
                    else (round(3.0 - (level - start) * 0.1, 4) if ptype == "CLEAN" else ""),
                    level if ptype == "SPREAD" else "",
                    round(18.0 + rng.gauss(0, 0.4), 3) if "CALL" in iid or "PUT" in iid else "",
                    bid,
                    ask,
                    level,
                    ptype,
                    "PRICING_LIB",
                    f"{day.isoformat()}T09:05:00Z",
                ]
            )
    write(
        "market_data",
        [
            "date",
            "instrument_id",
            "instrument_description",
            "asset_class",
            "price",
            "yield_pct",
            "spread_bps",
            "implied_vol_pct",
            "px_bid",
            "px_ask",
            "px_mid",
            "price_type",
            "source",
            "last_update_utc",
        ],
        md_rows,
    )

    # --- fx: every pair on every day -----------------------------------------
    fx_levels: dict[str, list[float]] = {}
    fx_rows = []
    for pair, base, quote, start in FX_PAIRS:
        vol = start * 0.0016
        fx_levels[pair] = [round(v, 4) for v in walk(rng, start, "LAST", 0)] or []
        level, series = start, []
        for _ in DAYS:
            series.append(round(level, 4))
            level += rng.gauss(start * 0.0002, vol)
        fx_levels[pair] = series
        for day, rate in zip(DAYS, series, strict=True):
            fx_rows.append([day.isoformat(), pair, base, quote, rate, "FXFEED"])
    write("fx_rates", ["date", "ccy_pair", "base_ccy", "quote_ccy", "spot_rate", "source"], fx_rows)

    def to_usd(amount: float, ccy: str, day: date) -> float:
        if ccy == "USD":
            return amount
        i = DAYS.index(day)
        for pair, base, quote, _ in FX_PAIRS:
            if base == "USD" and quote == ccy:
                return amount / fx_levels[pair][i]
            if base == ccy and quote == "USD":
                return amount * fx_levels[pair][i]
        raise KeyError(ccy)

    # --- the blotter ----------------------------------------------------------
    trade_rows = []
    for n, (tid, book, product, iid, ccy, notional, qty, price, direction, maturity) in enumerate(
        TRADES
    ):
        asset = {
            "IRS": "RATES",
            "GOVT_BOND": "RATES",
            "CORP_BOND": "CREDIT",
            "CDS": "CREDIT",
            "FX_SPOT": "FX",
            "FX_FORWARD": "FX",
            "FX_NDF": "FX",
            "EQ_OPTION": "EQUITY",
            "EQ_FUTURE": "EQUITY",
        }[product]
        traded_at = rng.randrange(0, 8)
        traded = DAYS[traded_at]
        # Business days, not calendar days: a settlement landing on a Saturday
        # gives an FX spot a closing date the market data has no quote for.
        settle = DAYS[min(traded_at + (2 if product.startswith("FX") else 3), len(DAYS) - 1)]
        cid, cname = COUNTERPARTIES[n % len(COUNTERPARTIES)]
        desc = (
            next(d for i, d, *_ in INSTRUMENTS if i == iid)
            if not product.startswith("FX")
            else f"{iid} {product.replace('FX_', '').lower()}"
        )
        trade_rows.append(
            [
                tid,
                BOOKS[book],
                f"TDR-D-{book + 1:02d}",
                traded.isoformat(),
                settle.isoformat(),
                asset,
                product,
                iid,
                desc,
                ccy,
                notional,
                qty,
                price,
                direction,
                cid,
                cname,
                "LIVE",
                maturity,
                "",
                f"REF-D-{n + 1:04d}",
            ]
        )
    write(
        "trades",
        [
            "trade_id",
            "book_id",
            "trader_id",
            "trade_date",
            "settle_date",
            "asset_class",
            "product_type",
            "instrument_id",
            "instrument_description",
            "currency",
            "notional",
            "quantity",
            "trade_price",
            "direction",
            "counterparty_id",
            "counterparty_name",
            "status",
            "maturity_date",
            "bloomberg_id",
            "internal_ref",
        ],
        trade_rows,
    )

    # --- risk file, consistent with the blotter so nothing reconciles red -----
    # The row builder takes its identifiers rather than closing over the loop:
    # a closure defined inside a loop reads the variable at call time, which is
    # correct here only by accident of being called immediately.
    def risk_row(tid, book, iid, metric: str, value: float, cur: str, unit: str) -> list:
        usd = value if unit == "amount_usd" else round(to_usd(value, cur, AS_OF), 2)
        return [
            AS_OF.isoformat(),
            tid,
            BOOKS[book],
            iid,
            metric,
            value,
            cur,
            usd,
            unit,
            f"{AS_OF.isoformat()}T06:30:00Z",
            "",
        ]

    risk_rows = []
    for tid, book, product, iid, ccy, notional, qty, _price, direction, maturity in TRADES:
        sign = 1 if direction in ("BUY", "RECEIVE") else -1
        years = (date.fromisoformat(maturity) - AS_OF).days / 365.25

        def row(metric: str, value: float, cur: str, unit: str, *, t=tid, b=book, i=iid) -> list:
            return risk_row(t, b, i, metric, value, cur, unit)

        if product == "IRS":
            risk_rows.append(row("DV01", round(sign * notional * years * 1e-4, 2), ccy, "amount"))
            risk_rows.append(row("Duration", round(years * 0.92, 4), ccy, "years"))
        elif product in ("GOVT_BOND", "CORP_BOND"):
            risk_rows.append(row("DV01", round(sign * notional * years * 0.9e-4, 2), ccy, "amount"))
            risk_rows.append(row("Duration", round(years * 0.88, 4), ccy, "years"))
            if product == "CORP_BOND":
                risk_rows.append(
                    row("Spread01", round(sign * notional * years * 0.8e-4, 2), ccy, "amount")
                )
                risk_rows.append(
                    row(
                        "JTD_USD",
                        round(-sign * to_usd(notional, ccy, AS_OF) * 0.6, 2),
                        "USD",
                        "amount_usd",
                    )
                )
        elif product == "CDS":
            risk_rows.append(
                row("CS01_USD", round(sign * notional * 4.6e-4, 2), "USD", "amount_usd")
            )
            risk_rows.append(row("JTD_USD", round(-sign * notional * 0.55, 2), "USD", "amount_usd"))
        elif product.startswith("FX"):
            risk_rows.append(
                row("Delta_USD", round(sign * to_usd(notional, ccy, AS_OF), 2), "USD", "amount_usd")
            )
        else:
            mult = 1_000.0
            spot = levels[iid][-1]
            delta = sign * qty * mult * spot
            risk_rows.append(
                row("Delta_USD", round(to_usd(delta, ccy, AS_OF), 2), "USD", "amount_usd")
            )
            if "CALL" in iid or "PUT" in iid:
                risk_rows.append(row("Vega_USD", round(abs(delta) * 0.004, 2), "USD", "amount_usd"))
                risk_rows.append(
                    row("Theta_USD", round(-abs(delta) * 0.0006, 2), "USD", "amount_usd")
                )
                risk_rows.append(
                    row("Gamma_USD", round(abs(delta) * 0.002, 2), "USD", "amount_usd")
                )
    write(
        "risk_sensitivities",
        [
            "as_of_date",
            "trade_id",
            "book_id",
            "instrument_id",
            "risk_metric",
            "value",
            "ccy",
            "value_usd",
            "unit",
            "computation_timestamp",
            "notes",
        ],
        risk_rows,
    )


if __name__ == "__main__":
    main()
