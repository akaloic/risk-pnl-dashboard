# tests/fixtures/

Hand-written, entirely synthetic CSVs used by the test suite. They mirror the
column layout of the real extracts and reproduce their known quirks, so the
cleaning and pricing logic can be tested on a fresh clone by someone who does
not have the confidential data.

Nothing here is copied from the real extracts: books, trade ids, counterparties
and prices are invented. Index contract identifiers (`NKY-FUT-2026-09`) follow
the same convention as the source files because the contract multiplier lookup
is keyed on them.

The numbers are chosen to be internally consistent and easy to verify by hand:

- `USDJPY = 150.0000` on the as-of date, so JPY/USD conversions are exact.
- `FIX-001` DV01 of 100,000 JPY -> 666.67 USD.
- `FIX-002` DV01 of -180,000 JPY -> -1,200.00 USD.
- `FIX-004` is 10 Nikkei futures at 38,500: 10 x 1,000 x 38,500 = 385,000,000
  JPY, i.e. 2,566,666.67 USD, which is the `Delta_USD` the risk file carries.
  That lets the contract multiplier be re-derived from the fixture the same way
  it was re-derived from the real risk file.

Deliberate quirks, each covered by a test:

| Fixture row | Quirk |
|---|---|
| `FIX-003` | `trade_date` as `MM/DD/YYYY` instead of ISO |
| `FIX-003` risk row | `risk_metric` spelled `DeltaUSD`, without the underscore |
