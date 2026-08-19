import { describe, expect, it } from "vitest";
import { type SortState, ariaSortFor, nextSort, sortRows } from "./sorting";

interface Row {
  book: string;
  qty: number;
}

const rows: Row[] = [
  { book: "FX-ASIA-01", qty: -4_000_000 },
  { book: "CREDIT-ASIA-01", qty: 15_000 },
  { book: "EQD-ASIA-01", qty: 250 },
  { book: "RATES-ASIA-01", qty: 10_000_000 },
];

const on = (key: keyof Row, direction: "asc" | "desc"): SortState<keyof Row> => ({
  key,
  direction,
});

describe("nextSort", () => {
  it("starts a new column descending", () => {
    // Largest first is the useful default on a risk table; nobody opens a
    // position blotter wanting the smallest line at the top.
    expect(nextSort(on("book", "asc"), "qty")).toEqual({ key: "qty", direction: "desc" });
  });

  it("reverses a column that is already sorted", () => {
    expect(nextSort(on("qty", "desc"), "qty")).toEqual({ key: "qty", direction: "asc" });
    expect(nextSort(on("qty", "asc"), "qty")).toEqual({ key: "qty", direction: "desc" });
  });
});

describe("sortRows", () => {
  it("orders numbers by magnitude, so a short ranks with a long of its size", () => {
    // Signed order would bury a 4m short below a 250 long, which is the
    // opposite of what a risk table is for.
    const sorted = sortRows(rows, on("qty", "desc"));

    expect(sorted.map((row) => row.qty)).toEqual([10_000_000, -4_000_000, 15_000, 250]);
  });

  it("reverses cleanly, smallest magnitude first", () => {
    const sorted = sortRows(rows, on("qty", "asc"));

    expect(sorted.map((row) => row.qty)).toEqual([250, 15_000, -4_000_000, 10_000_000]);
  });

  it("orders text alphabetically when ascending", () => {
    const sorted = sortRows(rows, on("book", "asc"));

    expect(sorted.map((row) => row.book)).toEqual([
      "CREDIT-ASIA-01",
      "EQD-ASIA-01",
      "FX-ASIA-01",
      "RATES-ASIA-01",
    ]);
  });

  it("does not mutate the array it was given", () => {
    const original = [...rows];
    sortRows(rows, on("qty", "desc"));

    expect(rows).toEqual(original);
  });

  it("handles an empty table", () => {
    expect(sortRows([], on("qty", "desc"))).toEqual([]);
  });
});

describe("ariaSortFor", () => {
  it("only reports an order on the column actually sorted", () => {
    // Every other header must say "none", or a screen reader announces four
    // columns all claiming to be the sorted one.
    expect(ariaSortFor(on("qty", "desc"), "qty")).toBe("descending");
    expect(ariaSortFor(on("qty", "asc"), "qty")).toBe("ascending");
    expect(ariaSortFor(on("qty", "desc"), "book")).toBe("none");
  });
});
