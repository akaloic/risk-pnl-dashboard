// @vitest-environment jsdom
/**
 * Coverage is the question asked before any risk total is trusted, so a book
 * the pricing library does not fully describe has to be visible as such.
 */

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { ReconciliationResponse } from "../api/types";
import { issue } from "../test/factories";
import { Reconciliation } from "./Reconciliation";

const recon = (over: Partial<ReconciliationResponse> = {}): ReconciliationResponse => ({
  as_of: "2026-08-05",
  coverage: [{ book_id: "FX-ASIA-01", trades: 10, with_risk: 10, coverage_pct: 100 }],
  issues: [],
  ...over,
});

describe("Reconciliation", () => {
  it("leads with how much of the blotter the risk file describes", () => {
    render(<Reconciliation recon={recon()} />);

    const row = within(screen.getAllByRole("table")[0]).getAllByRole("row")[1];
    expect(row.textContent).toMatch(/FX-ASIA-01/);
    expect(row.textContent).toMatch(/100/);
  });

  it("shows a book the library only partly covers", () => {
    // Partial coverage means the desk's risk totals understate the book, and
    // that is worth seeing before the totals are acted on.
    render(
      <Reconciliation
        recon={recon({
          coverage: [{ book_id: "RATES-ASIA-01", trades: 10, with_risk: 9, coverage_pct: 90 }],
        })}
      />,
    );

    expect(screen.getByText(/90/)).toBeDefined();
  });

  it("lists what failed to reconcile, with the treatment", () => {
    render(
      <Reconciliation
        recon={recon({
          issues: [
            issue({
              code: "TRADE_WITHOUT_RISK",
              entity_id: "TRD-011",
              detail: "the trade is in the blotter but carries no sensitivities",
            }),
          ],
        })}
      />,
    );

    expect(screen.getByText("TRD-011")).toBeDefined();
    expect(screen.getByText(/carries no sensitivities/)).toBeDefined();
  });

  it("says the two files agree rather than showing an empty list", () => {
    render(<Reconciliation recon={recon({ issues: [] })} />);

    expect(screen.getByText("Blotter against risk file")).toBeDefined();
  });
});
