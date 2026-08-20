"""Record the API as files, so the screen can be published without a server.

GitHub Pages runs no processes -- it hands out files. The screen wants an API,
so this drives the real one through FastAPI's own test client and writes down
every answer it gives. What gets published is therefore a recording of the API
rather than a mock of it: change a route's shape and the export changes with
it, so the published screen cannot quietly drift from the running one.

One directory per business day, because the date picker has to keep working on
the published copy, plus `latest/` for the call that names no date. The layout
mirrors the URLs exactly -- /pnl/trades becomes pnl/trades.json -- which is
what lets the frontend resolve one from the other with a single rule.

    python scripts/export_static_api.py          # -> frontend/public/api/

It reads demo-data/ and refuses to read data/. The export is built to be
published, and a figure derived from the confidential extracts is no more
publishable than the extracts themselves; a flag to override that would only
be there to be set by mistake.
"""

import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "frontend" / "public" / "api"

# Every path the frontend's api client asks for, in the shape it asks for it.
ENDPOINTS = (
    "/health",
    "/positions",
    "/pnl",
    "/pnl/trades",
    "/risk",
    "/counterparty",
    "/data-quality",
    "/reconciliation",
)


def data_directory() -> Path:
    """The demo desk, and nothing else."""
    chosen = Path(os.environ.get("RAD_DATA_DIR", REPO_ROOT / "demo-data")).resolve()
    if chosen == (REPO_ROOT / "data").resolve():
        sys.exit(
            "refusing to export from data/: the extracts are confidential and this "
            "output is published. Run scripts/make_demo_data.py and export that."
        )
    if not (chosen / "trades.csv").exists():
        sys.exit(f"no extracts in {chosen} -- run scripts/make_demo_data.py first")
    return chosen


def write(day: str | None, client) -> None:
    folder = OUT / (day or "latest")
    for path in ENDPOINTS:
        response = client.get(path, params={"as_of": day} if day else None)
        response.raise_for_status()
        target = folder / f"{path.lstrip('/')}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        # Compact: nothing reads this by eye, and every byte is served on load.
        target.write_text(json.dumps(response.json(), separators=(",", ":")))


def main() -> None:
    chosen = data_directory()
    os.environ["RAD_DATA_DIR"] = str(chosen)
    sys.path.insert(0, str(REPO_ROOT / "backend"))

    from fastapi.testclient import TestClient  # noqa: PLC0415 -- needs the env set first

    from app.main import app  # noqa: PLC0415

    if OUT.exists():
        # A stale day left behind from an earlier export would still be served.
        for stale in sorted(OUT.rglob("*"), reverse=True):
            stale.unlink() if stale.is_file() else stale.rmdir()

    with TestClient(app) as client:
        health = client.get("/health")
        health.raise_for_status()
        first = date.fromisoformat(health.json()["first_business_day"])
        last = date.fromisoformat(health.json()["last_business_day"])

        # Which days are business days is the API's opinion, not this script's:
        # a day it declines to price is a day the picker must not offer either.
        days = []
        day = first
        while day <= last:
            if client.get("/pnl", params={"as_of": day.isoformat()}).status_code == 200:
                days.append(day.isoformat())
            day += timedelta(days=1)

        for one in days:
            write(one, client)
        write(None, client)

    size = sum(path.stat().st_size for path in OUT.rglob("*.json"))
    print(f"{len(days)} business days from {chosen.name}/ -> {OUT.relative_to(REPO_ROOT)}")
    print(f"{len(days) + 1} directories, {size / 1024:.0f} kB")


if __name__ == "__main__":
    main()
