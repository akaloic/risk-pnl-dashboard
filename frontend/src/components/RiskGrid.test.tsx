// @vitest-environment jsdom
/**
 * The curve grid carries three claims that are invisible when wrong: the
 * columns run along the curve, the heavy cells are the ones that matter, and
 * the badges say something true about the row they sit on.
 */

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { riskResponse, tenor } from "../test/factories";
import { RiskGrid } from "./RiskGrid";

// The component renders three tables: risk by book, the curve, then tenors.
// Assertions scope to one of them, because the panel's own explanatory text
// repeats the words and figures the tests are looking for.
const BOOK_TABLE = 0;
const CURVE_TABLE = 1;

const table = (index: number) => screen.getAllByRole("table")[index] as HTMLTableElement;

const columns = () =>
  within(table(CURVE_TABLE))
    .getAllByRole("columnheader")
    .map((th) => th.textContent?.trim());

describe("RiskGrid", () => {
  it("runs the columns along the curve, not alphabetically", () => {
    // Sorted as text "10Y+" lands between "0-3M" and "1-3Y", and a risk manager
    // reads a curve that goes forwards, backwards, then forwards again.
    render(
      <RiskGrid
        risk={riskResponse({
          by_tenor: [
            tenor({ risk_metric: "DV01", tenor_bucket: "10Y+", open_usd: 466 }),
            tenor({ risk_metric: "DV01", tenor_bucket: "0-3M", open_usd: -202 }),
            tenor({ risk_metric: "DV01", tenor_bucket: "5-10Y", open_usd: 7_848 }),
          ],
        })}
      />,
    );

    expect(columns()).toEqual(["Book", "Metric", "0-3M", "5-10Y", "10Y+", "Net"]);
  });

  it("weights the cells that carry the row and leaves the rest alone", () => {
    // Same metric across buckets, so magnitudes are comparable. The -11.0m has
    // to read heavier than the -3.8m beside it or the eye lands nowhere.
    const { container } = render(
      <RiskGrid
        risk={riskResponse({
          by_tenor: [
            tenor({ risk_metric: "JTD_USD", tenor_bucket: "1-3Y", open_usd: -11_000_000 }),
            tenor({ risk_metric: "JTD_USD", tenor_bucket: "3-5Y", open_usd: -3_793_566 }),
          ],
        })}
      />,
    );

    const heavy = [...container.querySelectorAll("td.dominant")].map((td) => td.textContent);
    expect(heavy).toEqual(["-$11,000,000"]);
  });

  it("never weights a cell against a different metric", () => {
    // Down a column this would be a JTD against a CS01. If the grid ever
    // compared that way the heaviest figure on screen would be whichever
    // metric happens to be quoted in the largest units.
    const { container } = render(
      <RiskGrid
        risk={riskResponse({
          by_tenor: [
            tenor({ risk_metric: "JTD_USD", tenor_bucket: "1-3Y", open_usd: -11_000_000 }),
            tenor({ risk_metric: "CS01_USD", tenor_bucket: "1-3Y", open_usd: 4_500 }),
          ],
        })}
      />,
    );

    // One cell each: neither row has anything to be big against.
    expect(container.querySelectorAll("td.dominant")).toHaveLength(0);
  });

  it("marks a row holding exposure on both sides of zero", () => {
    render(
      <RiskGrid
        risk={riskResponse({
          by_tenor: [
            tenor({ risk_metric: "DV01", tenor_bucket: "3-5Y", open_usd: -1_670 }),
            tenor({ risk_metric: "DV01", tenor_bucket: "5-10Y", open_usd: 7_848 }),
          ],
        })}
      />,
    );

    expect(within(table(CURVE_TABLE)).getByText("curve")).toBeDefined();
  });

  it("says how much of a row rolls off inside the quarter", () => {
    render(
      <RiskGrid
        risk={riskResponse({
          by_tenor: [tenor({ tenor_bucket: "0-3M", open_usd: 37_924_168 })],
        })}
      />,
    );

    expect(within(table(CURVE_TABLE)).getByText(/rolls off · 100% ≤3M/)).toBeDefined();
  });

  it("surfaces settled risk as a figure, not a footnote", () => {
    // The risk file publishes delta for trades that have already paid. Showing
    // only the open column would leave a risk manager hunting the difference.
    render(
      <RiskGrid
        risk={riskResponse({
          by_book: [
            {
              book_id: "FX-ASIA-01",
              risk_metric: "Delta_USD",
              open_usd: 18_610_500,
              settled_usd: 19_438_300,
              total_usd: 38_048_800,
              trade_count: 10,
            },
          ],
        })}
      />,
    );

    expect(within(table(BOOK_TABLE)).getByText("$19,438,300")).toBeDefined();
  });

  it("renders a book with nothing on the curve without breaking", () => {
    render(<RiskGrid risk={riskResponse({ by_tenor: [] })} />);

    expect(screen.getByText("Open risk along the curve")).toBeDefined();
  });
});
