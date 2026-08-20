// @vitest-environment jsdom
/**
 * axe over every component, on what it actually renders.
 *
 * The linter reads the source and catches an attribute that is wrong on sight.
 * It does not catch a role with no container around it, or headers that are
 * fine alone and unassociated once the rows arrive. Those are properties of
 * the output.
 *
 * axe is not the whole answer either. Three of the four tabs pointed their
 * aria-controls at a panel id that was never in the document, because only the
 * selected panel was rendered, and axe passed the strip anyway. So the tab
 * pattern gets its own assertion below rather than being left to the scanner.
 *
 * This project shipped one of them and I missed it twice: `aria-selected` on
 * plain buttons, which is invalid because the attribute is only allowed on a
 * handful of roles, survived a deliberate accessibility pass. axe calls it
 * `aria-allowed-attr`, critical, in one line. That is the whole argument for
 * this file -- a check nobody runs is a check that does not exist, and two
 * careful readings were not one.
 *
 * Each component is rendered with data shaped like the real thing, because an
 * empty table has no header-to-cell association to get wrong.
 */

import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { expectNoViolations } from "../test/a11y";
import {
  book,
  daily,
  issue,
  pnlResponse,
  position,
  riskResponse,
  tenor,
  trade,
} from "../test/factories";
import App from "../App";
import { CounterpartyGrid } from "./CounterpartyGrid";
import { DataQualityPanel } from "./DataQualityPanel";
import { DeskSummary } from "./DeskSummary";
import { Empty, Loadable } from "./Loading";
import { PnlChart } from "./PnlChart";
import { PositionsTable } from "./PositionsTable";
import { Reconciliation } from "./Reconciliation";
import { RiskGrid } from "./RiskGrid";
import { TradeDetail } from "./TradeDetail";

const mockApi = vi.hoisted(() => ({
  health: vi.fn(),
  positions: vi.fn(),
  pnl: vi.fn(),
  pnlByTrade: vi.fn(),
  risk: vi.fn(),
  counterparty: vi.fn(),
  dataQuality: vi.fn(),
  reconciliation: vi.fn(),
}));
vi.mock("../api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/client")>()),
  api: mockApi,
}));
const { pnlByTrade } = mockApi;

const cases: [string, () => React.ReactElement][] = [
  [
    "DeskSummary",
    () => (
      <DeskSummary
        pnl={pnlResponse({ by_book: [book(), book({ book_id: "FX-ASIA-01" })] })}
        tenors={[tenor(), tenor({ book_id: "FX-ASIA-01", tenor_bucket: "Matured" })]}
        selected="EQD-ASIA-01"
        onSelect={() => {}}
      />
    ),
  ],
  [
    "PositionsTable",
    () => (
      <PositionsTable
        positions={[position(), position({ instrument_id: "USDJPY", position_status: "SETTLED" })]}
      />
    ),
  ],
  [
    "RiskGrid",
    () => (
      <RiskGrid
        risk={riskResponse({
          by_tenor: [
            tenor({ risk_metric: "DV01", tenor_bucket: "3-5Y", open_usd: -1_670 }),
            tenor({ risk_metric: "DV01", tenor_bucket: "5-10Y", open_usd: 7_848 }),
          ],
          per_trade_tenors: [
            {
              book_id: "RATES-ASIA-01",
              trade_id: "TRD-001",
              instrument_id: "JPY-IRS-10Y",
              risk_metric: "Duration",
              value: 0.9,
              unit: "years",
            },
          ],
        })}
      />
    ),
  ],
  [
    "CounterpartyGrid",
    () => (
      <CounterpartyGrid
        exposures={[
          {
            counterparty_id: "CPTY-01",
            counterparty_name: "Nomura Securities",
            open_trades: 9,
            settled_trades: 0,
            books: 3,
            gross_notional_usd: 51_900_559,
            current_exposure_usd: 131_898,
            net_mtm_usd: -149_211,
            share_of_exposure_pct: 34.07,
          },
        ]}
      />
    ),
  ],
  [
    "PnlChart",
    () => (
      <PnlChart
        series={[daily(), daily({ date: "2026-08-04", daily_usd: 400_000 })]}
        book={null}
      />
    ),
  ],
  [
    "DataQualityPanel",
    () => (
      <DataQualityPanel
        quality={{
          as_of: "2026-08-05",
          counts: { ERROR: 1, WARNING: 1 },
          issues: [issue(), issue({ severity: "WARNING", code: "STALE_QUOTE" })],
        }}
      />
    ),
  ],
  [
    "Reconciliation",
    () => (
      <Reconciliation
        recon={{
          as_of: "2026-08-05",
          coverage: [{ book_id: "FX-ASIA-01", trades: 10, with_risk: 10, coverage_pct: 100 }],
          issues: [issue({ code: "TRADE_WITHOUT_RISK", entity_id: "TRD-011" })],
        }}
      />
    ),
  ],
  ["Loadable error", () => <Loadable loading={false} error="failed" onRetry={() => {}}>x</Loadable>],
  ["Loadable loading", () => <Loadable loading error={null}>x</Loadable>],
  ["Empty", () => <Empty>No positions on this date.</Empty>],
];

describe("accessibility", () => {
  it.each(cases)("%s renders without violations", async (_name, element) => {
    const { container } = render(element());

    await expectNoViolations(container);
  });

  it("App's tab strip renders without violations", async () => {
    // Where the bug was: aria-selected on plain buttons, no tablist, no panel.
    // Testing the strip anywhere but here would have missed it, because the
    // components it switches between were each fine on their own.
    mockApi.health.mockResolvedValue({
      status: "ok",
      as_of: "2026-08-05",
      reporting_currency: "USD",
      trades: 40,
      business_days: 24,
      first_business_day: "2026-07-03",
      last_business_day: "2026-08-05",
    });
    mockApi.pnl.mockResolvedValue(pnlResponse());
    mockApi.positions.mockResolvedValue([position()]);
    mockApi.risk.mockResolvedValue(riskResponse());
    mockApi.counterparty.mockResolvedValue([]);
    mockApi.dataQuality.mockResolvedValue({ as_of: "2026-08-05", counts: {}, issues: [] });
    mockApi.reconciliation.mockResolvedValue({ as_of: "2026-08-05", coverage: [], issues: [] });

    const { container } = render(<App />);
    await waitFor(() => expect(screen.getAllByRole("tab")).toHaveLength(4));

    await expectNoViolations(container);
  });

  it("points every tab at a panel that is actually in the document", async () => {
    // What axe let through. aria-controls has to name an element that exists,
    // and with only the selected panel rendered, three of the four named
    // nothing. The panels now stay mounted and empty, hidden rather than
    // removed, so the reference holds whichever tab is open.
    mockApi.pnl.mockResolvedValue(pnlResponse());
    mockApi.positions.mockResolvedValue([position()]);
    mockApi.risk.mockResolvedValue(riskResponse());
    mockApi.counterparty.mockResolvedValue([]);
    mockApi.dataQuality.mockResolvedValue({ as_of: "2026-08-05", counts: {}, issues: [] });
    mockApi.reconciliation.mockResolvedValue({ as_of: "2026-08-05", coverage: [], issues: [] });

    render(<App />);
    await waitFor(() => expect(screen.getAllByRole("tab")).toHaveLength(4));

    const tabs = screen.getAllByRole("tab");
    for (const tab of tabs) {
      const panel = document.getElementById(tab.getAttribute("aria-controls") ?? "");
      expect(panel, `${tab.textContent} controls a panel that is not rendered`).not.toBeNull();
      // Exactly one is on show; the rest are hidden, which keeps them out of
      // the accessibility tree without breaking the reference.
      expect(panel?.hasAttribute("hidden")).toBe(tab.getAttribute("aria-selected") !== "true");
    }
    expect(tabs.filter((tab) => tab.getAttribute("aria-selected") === "true")).toHaveLength(1);
  });

  it("fails on a violation, so the check cannot quietly become a no-op", async () => {
    // An assertion helper that stops asserting passes every test it is in, and
    // an accessibility check nobody notices has gone quiet is worse than none:
    // it reads as evidence. This is the tab strip exactly as this project
    // shipped it -- aria-selected on a plain button, which the attribute does
    // not allow -- and axe has to still call it critical.
    //
    // Built as markup rather than JSX so the linter is not asked to accept a
    // deliberate defect: a standing lint warning teaches people to skim the
    // lint output, which is how the real one got through.
    const container = document.createElement("div");
    container.innerHTML = `<button type="button" aria-selected="true">Desk summary</button>`;
    document.body.append(container);

    await expect(expectNoViolations(container)).rejects.toThrow(/aria-allowed-attr/);
  });

  it("TradeDetail renders without violations once its data arrives", async () => {
    pnlByTrade.mockResolvedValue([
      trade(),
      trade({ trade_id: "TRD-039", pnl_usd: 103_301 }),
    ]);
    const { container } = render(
      <TradeDetail book="EQD-ASIA-01" asOf="2026-08-05" expected={-10_147} onClose={() => {}} />,
    );

    await waitFor(() => expect(screen.getByText("TRD-034")).toBeDefined());
    await expectNoViolations(container);
  });
});
