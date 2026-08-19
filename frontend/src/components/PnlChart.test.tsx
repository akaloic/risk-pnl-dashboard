// @vitest-environment jsdom
/**
 * The chart is hand-drawn SVG, so an axis or a bar that is wrong is wrong
 * silently -- it still draws a chart, just not of these numbers.
 */

import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { daily } from "../test/factories";
import { PnlChart } from "./PnlChart";

const month = [
  daily({ date: "2026-08-03", book_id: "EQD-ASIA-01", daily_usd: 400_000, cumulative_usd: 400_000 }),
  daily({ date: "2026-08-03", book_id: "FX-ASIA-01", daily_usd: -100_000, cumulative_usd: -100_000 }),
  daily({ date: "2026-08-04", book_id: "EQD-ASIA-01", daily_usd: -50_000, cumulative_usd: 350_000 }),
  daily({ date: "2026-08-04", book_id: "FX-ASIA-01", daily_usd: -20_000, cumulative_usd: -120_000 }),
];

const ticks = (container: HTMLElement) =>
  [...container.querySelectorAll("svg text")]
    .map((node) => node.textContent ?? "")
    .filter((text) => text.includes("$"));

describe("PnlChart", () => {
  it("labels the axis on round numbers, not on the data's own extremes", () => {
    // An axis reading $906,542 looks like a stray print rather than a boundary.
    const { container } = render(<PnlChart series={month} book={null} />);

    for (const tick of ticks(container)) {
      expect(tick).toMatch(/^-?\$(0|[1-9]\d*(,\d{3})*)$/);
    }
    expect(ticks(container)).toContain("$0");
  });

  it("adds the books together into one bar a day", () => {
    const { container } = render(<PnlChart series={month} book={null} />);

    // Two dates in, two bars out -- not four.
    expect(container.querySelectorAll("rect[fill='#3fbf7f'], rect[fill='#f2545b']")).toHaveLength(2);
  });

  it("rescales when the chart is filtered to one book", () => {
    // Desk scale would flatten a single book against the baseline.
    const { container, rerender } = render(<PnlChart series={month} book={null} />);
    const deskTop = Math.max(...ticks(container).map((t) => Number(t.replace(/[$,]/g, ""))));

    rerender(<PnlChart series={month} book="FX-ASIA-01" />);
    const bookTop = Math.max(...ticks(container).map((t) => Number(t.replace(/[$,]/g, ""))));

    expect(bookTop).toBeLessThan(deskTop);
  });

  it("describes itself for a reader who cannot see it", () => {
    render(<PnlChart series={month} book={null} />);

    expect(screen.getByRole("img").getAttribute("aria-label")).toMatch(
      /Daily and cumulative P&L in USD/,
    );
  });

  it("says there is nothing to draw rather than drawing nothing", () => {
    render(<PnlChart series={[]} book={null} />);

    expect(screen.getByText(/No P&L for this period/)).toBeDefined();
  });

  it("handles a book with no rows in the series", () => {
    render(<PnlChart series={month} book="RATES-ASIA-01" />);

    expect(screen.getByText(/No P&L for this period/)).toBeDefined();
  });
});
