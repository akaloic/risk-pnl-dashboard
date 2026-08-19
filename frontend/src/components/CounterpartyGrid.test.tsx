// @vitest-environment jsdom
/**
 * The view exists to keep two questions apart: how big is this relationship,
 * and what does it cost if they stop paying. A screen that conflates them
 * points a credit officer at the wrong name.
 */

import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { CounterpartyExposure } from "../api/types";
import { CounterpartyGrid } from "./CounterpartyGrid";

const party = (over: Partial<CounterpartyExposure> = {}): CounterpartyExposure => ({
  counterparty_id: "CPTY-01",
  counterparty_name: "Nomura Securities",
  open_trades: 9,
  settled_trades: 0,
  books: 3,
  gross_notional_usd: 51_900_559,
  current_exposure_usd: 131_898,
  net_mtm_usd: -149_211,
  share_of_exposure_pct: 34.07,
  ...over,
});

const names = () =>
  within(screen.getByRole("table"))
    .getAllByRole("row")
    .slice(1)
    .map((tr) => tr.children[0].textContent?.trim());

describe("CounterpartyGrid", () => {
  it("keeps the order the backend ranked, which is by exposure", () => {
    render(
      <CounterpartyGrid
        exposures={[
          party({ counterparty_id: "A", counterparty_name: "Nomura", current_exposure_usd: 131_898 }),
          party({ counterparty_id: "B", counterparty_name: "HSBC", current_exposure_usd: 94_503 }),
        ]}
      />,
    );

    expect(names()).toEqual(["Nomura", "HSBC"]);
  });

  it("marks a large relationship that costs nothing to lose", () => {
    // 10m of business against a name that owes the desk nothing. A limit set
    // on notional would flag this; a limit set on exposure would not.
    render(
      <CounterpartyGrid
        exposures={[
          party({ counterparty_name: "Citi", current_exposure_usd: 0, gross_notional_usd: 10_000_000 }),
        ]}
      />,
    );

    expect(screen.getByText("no exposure")).toBeDefined();
  });

  it("does not call a counterparty exposure-free when it has no business either", () => {
    render(
      <CounterpartyGrid
        exposures={[party({ current_exposure_usd: 0, gross_notional_usd: 0 })]}
      />,
    );

    expect(screen.queryByText("no exposure")).toBeNull();
  });

  it("shows a relationship the desk is losing on as still being owed money", () => {
    // Net -149,211 and exposure 131,898: the desk is down on the relationship
    // and would still lose 131,898 if the name defaulted tomorrow.
    render(<CounterpartyGrid exposures={[party()]} />);

    const row = within(screen.getByRole("table")).getAllByRole("row")[1];
    expect(row.textContent).toMatch(/\$131,898/);
    expect(row.textContent).toMatch(/-\$149,211/);
  });

  it("says who the concentration is with, above the table", () => {
    // The number is in the grid too; what matters is that a reader is told the
    // headline without having to compute it from the rows.
    const { container } = render(
      <CounterpartyGrid
        exposures={[party({ counterparty_name: "Nomura", share_of_exposure_pct: 34.07 })]}
      />,
    );

    const hint = container.querySelector(".hint") as HTMLElement;
    expect(hint.textContent).toMatch(/Nomura carries 34.07%/);
  });

  it("weights the names that carry the exposure", () => {
    const { container } = render(
      <CounterpartyGrid
        exposures={[
          party({ counterparty_id: "A", current_exposure_usd: 131_898 }),
          party({ counterparty_id: "B", current_exposure_usd: 3_241 }),
        ]}
      />,
    );

    const heavy = [...container.querySelectorAll("td.dominant")].map((td) => td.textContent);
    expect(heavy).toEqual(["$131,898"]);
  });

  it("renders an empty desk without dividing by zero", () => {
    render(<CounterpartyGrid exposures={[]} />);

    expect(screen.getByText("Counterparty exposure")).toBeDefined();
  });
});
