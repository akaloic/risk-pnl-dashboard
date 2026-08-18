# data/

This directory is where the four confidential source extracts belong. They are
**not** committed to the repository (`data/*.csv` is excluded in `.gitignore`) —
drop your own copies here before running the backend:

```
data/trades.csv
data/market_data.csv
data/risk_sensitivities.csv
data/fx_rates.csv
```

The backend reads from this directory by default (override with the
`RAD_DATA_DIR` environment variable, which is how the test suite points at
`tests/fixtures/` instead). See the top-level `README.md` for how the field
layout of each file is expected to look, and `tests/fixtures/` for small
hand-written examples that exercise the known data quality issues without
needing the real extracts.
