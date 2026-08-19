// @vitest-environment jsdom
/**
 * Sorting is the one interaction in this table, and a comparator that is
 * subtly wrong still produces a table that looks perfectly ordered.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { position } from "../test/factories";
import { PositionsTable } from "./PositionsTable";

const rows = () =>
  within(screen.getByRole("table"))
    .getAllByRole("row")
    .slice(1)
    .map((tr) => tr.children[0].textContent?.trim());

const notionals = () =>
  within(screen.getByRole("table"))
    .getAllByRole("row")
    .slice(1)
    .map((tr) => tr.children[6].textContent?.trim());

const sample = [
  position({ book_id: "FX-ASIA-01", instrument_id: "USDJPY", net_notional: -10_000_000 }),
  position({ book_id: "CREDIT-ASIA-01", instrument_id: "CDB-3.4-2028", net_notional: 5_000_000 }),
  position({ book_id: "EQD-ASIA-01", instrument_id: "NKY-FUT-2026-09", net_notional: 0 }),
];

describe("PositionsTable", () => {
  it("offers a sort on every column, not half of them", () => {
    // Four of nine sorting taught a user the table does not sort at all.
    render(<PositionsTable positions={sample} />);

    const headers = within(screen.getByRole("table")).getAllByRole("columnheader");
    const sortable = headers.filter((th) => within(th).queryByRole("button"));

    expect(sortable).toHaveLength(headers.length);
  });

  it("ranks a large short with a large long, not below every long", async () => {
    // Magnitude, not value. Signed order would bury a -10m behind a 0.
    render(<PositionsTable positions={sample} />);

    await userEvent.click(screen.getByRole("button", { name: /Net notional/ }));

    expect(notionals()).toEqual(["-10,000,000", "5,000,000", "0"]);
  });

  it("reverses when the sorted column is clicked again", async () => {
    render(<PositionsTable positions={sample} />);
    const header = screen.getByRole("button", { name: /Net notional/ });

    await userEvent.click(header);
    await userEvent.click(header);

    expect(notionals()).toEqual(["0", "5,000,000", "-10,000,000"]);
  });

  it("announces the order on the sorted column and nowhere else", async () => {
    render(<PositionsTable positions={sample} />);

    await userEvent.click(screen.getByRole("button", { name: /Net notional/ }));

    const headers = within(screen.getByRole("table")).getAllByRole("columnheader");
    const announced = headers.map((th) => th.getAttribute("aria-sort"));
    expect(announced.filter((value) => value !== "none")).toEqual(["descending"]);
  });

  it("hides settled positions when asked, and says how many are left", async () => {
    render(
      <PositionsTable
        positions={[...sample, position({ instrument_id: "SETTLED-ONE", position_status: "SETTLED" })]}
      />,
    );

    expect(rows()).toHaveLength(4);
    await userEvent.click(screen.getByRole("checkbox"));

    expect(rows()).toHaveLength(3);
  });

  it("says so rather than rendering an empty table", () => {
    render(<PositionsTable positions={[]} />);

    expect(screen.getByText(/No positions on this date/)).toBeDefined();
  });
});
