"""API integration tests.

The engines are tested on their own elsewhere; what matters here is that the
routes hand back the same numbers, that the wire format is JSON a browser can
actually parse, and that a bad request is refused with an explanation rather
than a stack trace.
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.analytics import desk_summary
from app.dataset import load_dataset
from app.main import app
from app.report import full_quality_report

AS_OF = "2026-08-05"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def data():
    return load_dataset()


# --- service -----------------------------------------------------------------


def test_health_reports_what_was_loaded(client, data):
    body = client.get("/health").json()

    assert body["status"] == "ok"
    assert body["reporting_currency"] == "USD"
    assert body["trades"] == len(data.trades)
    assert body["business_days"] == len(data.business_days)


def test_openapi_schema_is_published(client):
    """The frontend's typed client is generated against this contract."""
    schema = client.get("/openapi.json").json()

    assert "/positions" in schema["paths"]
    assert "/data-quality" in schema["paths"]


# --- positions ---------------------------------------------------------------


def test_positions_match_the_engine(client, data):
    from app.positions import build_positions

    body = client.get("/positions").json()
    expected = build_positions(data.trades, as_of=date(2026, 8, 5)).positions

    assert len(body) == len(expected)
    assert {row["instrument_id"] for row in body} == set(expected["instrument_id"])


def test_positions_expose_settlement_state(client):
    body = client.get("/positions").json()
    statuses = {row["position_status"] for row in body}

    assert statuses <= {"OPEN", "SETTLED"}
    assert "SETTLED" in statuses


def test_positions_replay_an_earlier_date(client):
    """The same endpoint has to answer for any business day of the month."""
    august = client.get("/positions", params={"date": AS_OF}).json()
    july = client.get("/positions", params={"date": "2026-07-02"}).json()

    assert len(july) < len(august)


# --- P&L ---------------------------------------------------------------------


def test_pnl_matches_the_desk_summary(client, data):
    body = client.get("/pnl").json()
    expected = desk_summary(data, as_of=date(2026, 8, 5))

    assert body["as_of"] == AS_OF
    assert body["total_inception_usd"] == pytest.approx(expected["inception_usd"].sum())
    assert len(body["by_book"]) == len(expected)


def test_pnl_series_and_cards_agree(client):
    """A card and the chart beside it must not disagree on the wire either."""
    body = client.get("/pnl").json()

    final = {
        row["book_id"]: row for row in body["series"] if row["date"] == body["as_of"]
    }
    for card in body["by_book"]:
        assert card["inception_usd"] == pytest.approx(final[card["book_id"]]["cumulative_usd"])
        assert card["day_usd"] == pytest.approx(final[card["book_id"]]["daily_usd"])


def test_pnl_is_replayable_over_the_month(client):
    """Valuing an earlier day returns a shorter series ending on that day."""
    body = client.get("/pnl", params={"date": "2026-07-30"}).json()

    assert body["as_of"] == "2026-07-30"
    assert max(row["date"] for row in body["series"]) == "2026-07-30"


def test_pnl_by_trade_reconciles_to_the_book_totals(client):
    trades = client.get("/pnl/trades").json()
    books = client.get("/pnl").json()["by_book"]

    by_book: dict[str, float] = {}
    for row in trades:
        by_book[row["book_id"]] = by_book.get(row["book_id"], 0.0) + row["pnl_usd"]

    for card in books:
        assert by_book[card["book_id"]] == pytest.approx(card["inception_usd"])


def test_pnl_detail_shows_the_levels_behind_the_number(client):
    """A P&L nobody can take apart is a P&L nobody will trust."""
    row = client.get("/pnl/trades").json()[0]

    assert {"method", "reference_level", "current_level", "valuation_date"} <= set(row)


# --- risk --------------------------------------------------------------------


def test_risk_splits_settled_exposure_out(client):
    body = client.get("/risk").json()
    fx_delta = [
        row
        for row in body["by_book"]
        if row["book_id"] == "FX-TEST-01" and row["risk_metric"] == "Delta_USD"
    ]

    assert len(fx_delta) == 1
    assert fx_delta[0]["settled_usd"] != 0
    assert fx_delta[0]["total_usd"] == pytest.approx(
        fx_delta[0]["open_usd"] + fx_delta[0]["settled_usd"]
    )


def test_risk_never_sums_a_tenor(client):
    body = client.get("/risk").json()

    assert "Duration" not in {row["risk_metric"] for row in body["by_book"]}
    assert "Duration" in {row["risk_metric"] for row in body["per_trade_tenors"]}


# --- quality -----------------------------------------------------------------


def test_data_quality_returns_every_finding(client, data):
    body = client.get("/data-quality").json()
    expected = full_quality_report(data, as_of=date(2026, 8, 5))

    assert len(body["issues"]) == len(expected)
    assert sum(body["counts"].values()) == len(expected)


def test_every_finding_carries_its_treatment(client):
    """The panel exists so a number can be challenged and explained."""
    for issue in client.get("/data-quality").json()["issues"]:
        assert issue["treatment"].strip()
        assert issue["detail"].strip()


def test_findings_are_ordered_worst_first(client):
    rank = {"ERROR": 0, "WARNING": 1, "INFO": 2}
    severities = [rank[issue["severity"]] for issue in client.get("/data-quality").json()["issues"]]

    assert severities == sorted(severities)


def test_reconciliation_reports_coverage_and_findings(client, data):
    body = client.get("/reconciliation").json()

    assert {row["book_id"] for row in body["coverage"]} == set(data.trades["book_id"])
    assert any(
        issue["code"] == "SETTLED_TRADE_CARRIES_RISK" for issue in body["issues"]
    )


# --- contract and failure modes ----------------------------------------------


def test_an_unpublished_date_is_a_client_error_with_an_explanation(client):
    """A weekend is the caller's mistake, and the message names the range."""
    response = client.get("/pnl", params={"date": "2026-08-08"})

    assert response.status_code == 400
    assert "business day" in response.json()["detail"]


def test_a_malformed_date_is_rejected(client):
    assert client.get("/positions", params={"date": "not-a-date"}).status_code == 422


def test_responses_carry_no_nan(client):
    """NaN is not valid JSON; a leaked one breaks the browser, not the server."""
    import json

    for path in ("/positions", "/pnl", "/risk", "/data-quality", "/reconciliation"):
        raw = client.get(path).text
        assert "NaN" not in raw
        assert "Infinity" not in raw
        json.loads(raw)


def test_nulls_survive_as_json_null(client):
    """A missing maturity must arrive as null, not as the string 'NaT'."""
    body = client.get("/positions").json()

    assert all(row["maturity_date"] is None or "-" in row["maturity_date"] for row in body)
