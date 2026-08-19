// @vitest-environment jsdom
/**
 * The card grid is where the badge logic meets the screen. The pure functions
 * behind it are tested in lib/; what these check is that the component asks
 * them the right question and shows the answer.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { book, pnlResponse, tenor } from "../test/factories";
import { DeskSummary } from "./DeskSummary";

const noop = () => {};

describe("DeskSummary", () => {
  it("leads with the day figure and keeps inception underneath", () => {
    render(
      <DeskSummary
        pnl={pnlResponse({ total_day_usd: -178_379, total_inception_usd: -443_715 })}
        selected={null}
        onSelect={noop}
      />,
    );

    const total = screen.getByText("DESK TOTAL").closest(".card") as HTMLElement;
    expect(within(total).getByText("-$178,379")).toBeDefined();
    expect(within(total).getByText("-$443,715")).toBeDefined();
  });

  it("badges a book whose every risk metric matures inside the quarter", () => {
    render(
      <DeskSummary
        pnl={pnlResponse({ by_book: [book({ book_id: "EQD-ASIA-01" })] })}
        tenors={[tenor({ book_id: "EQD-ASIA-01", tenor_bucket: "0-3M" })]}
        selected={null}
        onSelect={noop}
      />,
    );

    expect(screen.getByText("rolls off ≤3M")).toBeDefined();
  });

  it("leaves a book with far-dated risk unbadged", () => {
    // The badge claims *all* of the book rolls off. A book holding anything
    // past the quarter must not carry it, or the claim is a lie.
    render(
      <DeskSummary
        pnl={pnlResponse({ by_book: [book({ book_id: "RATES-ASIA-01" })] })}
        tenors={[
          tenor({ book_id: "RATES-ASIA-01", risk_metric: "DV01", tenor_bucket: "5-10Y" }),
        ]}
        selected={null}
        onSelect={noop}
      />,
    );

    expect(screen.queryByText("rolls off ≤3M")).toBeNull();
  });

  it("shows no badge at all while the risk call is still in flight", () => {
    // `tenors` is undefined until /risk lands. Rendering a badge off missing
    // data would flash a claim the tool cannot yet support.
    render(<DeskSummary pnl={pnlResponse()} selected={null} onSelect={noop} />);

    expect(screen.queryByText("rolls off ≤3M")).toBeNull();
  });

  it("hands the book id back when a card is clicked", async () => {
    const onSelect = vi.fn();
    render(
      <DeskSummary
        pnl={pnlResponse({ by_book: [book({ book_id: "FX-ASIA-01" })] })}
        selected={null}
        onSelect={onSelect}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: /FX-ASIA-01/ }));

    expect(onSelect).toHaveBeenCalledWith("FX-ASIA-01");
  });

  it("clears the selection when the open card is clicked again", async () => {
    const onSelect = vi.fn();
    render(
      <DeskSummary
        pnl={pnlResponse({ by_book: [book({ book_id: "FX-ASIA-01" })] })}
        selected="FX-ASIA-01"
        onSelect={onSelect}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: /FX-ASIA-01/ }));

    expect(onSelect).toHaveBeenCalledWith(null);
  });

  it("gives each card an accessible name and an expanded state", () => {
    // The card is a wall of figures; without a name a screen reader announces
    // the numbers and never says which book they belong to.
    render(
      <DeskSummary
        pnl={pnlResponse({ by_book: [book({ book_id: "FX-ASIA-01" })] })}
        selected="FX-ASIA-01"
        onSelect={noop}
      />,
    );

    const card = screen.getByRole("button", { name: /FX-ASIA-01/ });
    expect(card.getAttribute("aria-expanded")).toBe("true");
  });
});
