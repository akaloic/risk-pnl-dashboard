// @vitest-environment jsdom
/**
 * The panel that makes every other number defensible. Its one job is that no
 * finding is shown without the treatment applied to it.
 */

import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import type { DataQualityResponse } from "../api/types";
import { issue } from "../test/factories";
import { DataQualityPanel } from "./DataQualityPanel";

const report = (over: Partial<DataQualityResponse> = {}): DataQualityResponse => ({
  as_of: "2026-08-05",
  counts: { ERROR: 1, WARNING: 1, INFO: 1 },
  issues: [
    issue({ severity: "ERROR", code: "DUPLICATE_TRADE_ROW", entity_id: "TRD-015" }),
    issue({ severity: "WARNING", code: "STALE_QUOTE", entity_id: "CDB-3.4-2028" }),
    issue({ severity: "INFO", code: "QUOTE_WITHOUT_POSITION", entity_id: "SPX" }),
  ],
  ...over,
});

const bodyRows = () =>
  within(screen.getByRole("table")).getAllByRole("row").slice(1);

describe("DataQualityPanel", () => {
  it("never shows a finding without what was done about it", async () => {
    // The treatment column is the point of the panel: a disputed figure is only
    // defensible if the tool can say what it changed underneath it.
    render(<DataQualityPanel quality={report()} />);

    for (const row of bodyRows()) {
      expect(row.lastElementChild?.textContent?.trim()).not.toBe("");
    }
  });

  it("narrows to one severity and back", async () => {
    render(<DataQualityPanel quality={report()} />);
    expect(bodyRows()).toHaveLength(3);

    await userEvent.click(screen.getByRole("button", { name: /ERROR/ }));
    expect(bodyRows()).toHaveLength(1);
    expect(screen.getByText("TRD-015")).toBeDefined();

    await userEvent.click(screen.getByRole("button", { name: /ALL/ }));
    expect(bodyRows()).toHaveLength(3);
  });

  it("names the prose columns on the cells, for when the header row is gone", () => {
    // Below desk width the findings stack into blocks and the header row is
    // hidden, so a cell's data-label is the only thing naming it. The two
    // columns that need it are the two that look alike: a paragraph of what
    // was found and a paragraph of what was done about it. Unlabelled, the
    // panel stops making the one distinction it exists to make.
    render(<DataQualityPanel quality={report()} />);

    const columns = within(screen.getByRole("table"))
      .getAllByRole("columnheader")
      .map((header) => header.textContent);
    const cells = [...bodyRows()[0].children];

    expect(cells.filter((cell) => cell.hasAttribute("data-label"))).toHaveLength(2);
    cells.forEach((cell, index) => {
      const label = cell.getAttribute("data-label");
      // A label that no longer matches its column heading is worse than none:
      // it names the value wrongly on the only screen that shows it.
      if (label !== null) expect(label).toBe(columns[index]);
    });
  });

  it("reports a clean extract as clean rather than as an empty table", () => {
    render(<DataQualityPanel quality={report({ counts: {}, issues: [] })} />);

    expect(screen.queryByRole("table")).toBeNull();
  });
});
