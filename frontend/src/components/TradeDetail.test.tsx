// @vitest-environment jsdom
/**
 * The drill-down makes a headline arguable, so its two claims have to hold: the
 * rows tie back to the card above, and a line that is half a position says so.
 */

import { render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import { trade } from "../test/factories";
import { TradeDetail } from "./TradeDetail";

const { pnlByTrade } = vi.hoisted(() => ({ pnlByTrade: vi.fn() }));
vi.mock("../api/client", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/client")>()),
  api: { pnlByTrade },
}));

const show = (rows: ReturnType<typeof trade>[], expected: number) => {
  pnlByTrade.mockResolvedValue(rows);
  return render(
    <TradeDetail book="EQD-ASIA-01" asOf="2026-08-05" expected={expected} onClose={() => {}} />,
  );
};

describe("TradeDetail", () => {
  it("shows only the book that was drilled into", async () => {
    show(
      [
        trade({ trade_id: "TRD-034", book_id: "EQD-ASIA-01" }),
        trade({ trade_id: "TRD-001", book_id: "RATES-ASIA-01" }),
      ],
      -113_448.1,
    );

    await waitFor(() => expect(screen.getByText("TRD-034")).toBeDefined());
    expect(screen.queryByText("TRD-001")).toBeNull();
  });

  it("leads with the biggest contributor, whichever way it moved", async () => {
    show(
      [
        trade({ trade_id: "SMALL", pnl_usd: 2_736 }),
        trade({ trade_id: "BIGGEST", pnl_usd: -113_448 }),
        trade({ trade_id: "MIDDLE", pnl_usd: 51_756 }),
      ],
      -58_956,
    );

    await waitFor(() => expect(screen.getByText("BIGGEST")).toBeDefined());
    const ids = within(screen.getByRole("table"))
      .getAllByRole("row")
      .slice(1, 4)
      .map((tr) => tr.children[0].textContent);
    expect(ids).toEqual(["BIGGEST", "MIDDLE", "SMALL"]);
  });

  it("says when two rows are one position, and what it nets to", async () => {
    // The case this exists for: read as separate lines, the worst trade on the
    // desk looks eleven times worse than the position actually is.
    show(
      [
        trade({ trade_id: "TRD-034", instrument_id: "NKY-FUT-2026-09", pnl_usd: -113_448 }),
        trade({ trade_id: "TRD-039", instrument_id: "NKY-FUT-2026-09", pnl_usd: 103_301 }),
      ],
      -10_147,
    );

    await waitFor(() => expect(screen.getAllByText(/leg · net/)).toHaveLength(2));
    expect(screen.getAllByText("leg · net -$10,147")).toHaveLength(2);
  });

  it("leaves a trade that is a position on its own unmarked", async () => {
    show([trade({ trade_id: "TRD-005", instrument_id: "JGB-0.5-2033" })], -113_448.1);

    await waitFor(() => expect(screen.getByText("TRD-005")).toBeDefined());
    expect(screen.queryByText(/leg · net/)).toBeNull();
  });

  it("keeps a spot and a forward on one pair apart", async () => {
    // They close on different dates, so they are two positions. Grouping on the
    // instrument alone would net them and invent a hedge.
    show(
      [
        trade({ trade_id: "TRD-021", instrument_id: "USDJPY", product_type: "FX_SPOT" }),
        trade({ trade_id: "TRD-028", instrument_id: "USDJPY", product_type: "FX_FORWARD" }),
      ],
      -1,
    );

    await waitFor(() => expect(screen.getByText("TRD-021")).toBeDefined());
    expect(screen.queryByText(/leg · net/)).toBeNull();
  });

  it("warns when the rows do not add up to the card above", async () => {
    // Silence here would let two screens disagree without either being wrong
    // on its own terms.
    show([trade({ pnl_usd: -100 })], -999_999);

    await waitFor(() =>
      expect(screen.getByText(/does not tie to the book total/)).toBeDefined(),
    );
  });

  it("stays quiet when they do", async () => {
    show([trade({ pnl_usd: -113_448.1 })], -113_448.1);

    await waitFor(() => expect(screen.getByText("TRD-034")).toBeDefined());
    expect(screen.queryByText(/does not tie/)).toBeNull();
  });

  it("carries the backend's explanation through to the screen", async () => {
    pnlByTrade.mockRejectedValue(new ApiError("2026-08-08 is not a business day", 400));
    render(
      <TradeDetail book="EQD-ASIA-01" asOf="2026-08-08" expected={0} onClose={() => {}} />,
    );

    await waitFor(() =>
      expect(screen.getByText(/is not a business day/)).toBeDefined(),
    );
  });
});
