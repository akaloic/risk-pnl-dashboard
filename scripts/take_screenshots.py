"""Capture the screenshots the README shows, from the demo dataset.

Scripted rather than taken by hand so the images can be regenerated when the
screens change, and so it is obvious they came from demo-data/ -- the desk in
them is invented, and nothing derived from the confidential extracts is ever
committed to this repository.

    python scripts/make_demo_data.py
    RAD_DATA_DIR=demo-data PYTHONPATH=backend uvicorn app.main:app &
    cd frontend && npm run dev &
    <scratch-venv>/bin/python scripts/take_screenshots.py

Playwright drives a real Chrome rather than downloading its own: the tab strip
holds its state in React, so there is no URL to point a plain screenshot tool
at, and the views have to be clicked through.
"""

import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

APP = "http://localhost:5173"
OUT = Path(__file__).resolve().parents[1] / "docs" / "screenshots"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


# Captured at 2x for sharp text, then halved: GitHub renders a README image at
# about 900px, so shipping 2880 costs the repository weight it never displays.
WIDTH = 1600


def shoot(page, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    page.wait_for_timeout(700)
    path = OUT / f"{name}.png"
    page.screenshot(path=str(path))
    subprocess.run(["sips", "-Z", str(WIDTH), str(path)], check=True, capture_output=True)
    print(f"  docs/screenshots/{name}.png")


def main() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME)
        page = browser.new_page(viewport={"width": 1440, "height": 1000}, device_scale_factor=2)
        page.goto(APP, wait_until="networkidle")
        page.wait_for_selector("text=DESK TOTAL", timeout=15_000)

        shoot(page, "01-desk-summary")

        # The drill-down: the second card, whose book holds both legs of a future.
        page.get_by_role("button", name="EQD-DEMO-01", exact=False).click()
        page.wait_for_selector("text=P&L by trade")
        shoot(page, "02-trade-detail")
        page.get_by_role("button", name="EQD-DEMO-01", exact=False).click()

        page.get_by_role("tab", name="Positions").click()
        page.wait_for_selector("table")
        shoot(page, "03-positions")

        page.get_by_role("tab", name="Risk").click()
        page.wait_for_selector("text=Open risk along the curve")
        shoot(page, "04-risk")
        page.get_by_text("Counterparty exposure").scroll_into_view_if_needed()
        shoot(page, "05-counterparty")

        page.get_by_role("tab", name="Data quality").click()
        page.wait_for_selector("text=Treatment applied")
        shoot(page, "06-data-quality")

        browser.close()


if __name__ == "__main__":
    try:
        main()
    except Exception as failure:  # noqa: BLE001 -- a script, not a library
        sys.exit(f"screenshots failed: {failure}\nAre both servers running?")
