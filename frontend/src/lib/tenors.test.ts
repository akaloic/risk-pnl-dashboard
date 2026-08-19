import { describe, expect, it } from "vitest";
import type { TenorExposure } from "../api/types";
import { booksRollingOff, isCurvePosition, nearTermShare, pivotByTenor } from "./tenors";

const cell = (
  book: string,
  metric: string,
  bucket: string,
  usd: number,
): TenorExposure => ({
  book_id: book,
  risk_metric: metric,
  tenor_bucket: bucket,
  open_usd: usd,
  trade_count: 1,
});

describe("pivotByTenor", () => {
  it("orders the columns along the curve, not alphabetically", () => {
    // The failure this exists to prevent: sorted as text, "10Y+" lands between
    // "0-3M" and "1-3Y" and the curve reads back to front.
    const { buckets } = pivotByTenor([
      cell("RATES-ASIA-01", "DV01", "10Y+", 1),
      cell("RATES-ASIA-01", "DV01", "0-3M", 1),
      cell("RATES-ASIA-01", "DV01", "5-10Y", 1),
      cell("RATES-ASIA-01", "DV01", "1-3Y", 1),
    ]);

    expect(buckets).toEqual(["0-3M", "1-3Y", "5-10Y", "10Y+"]);
  });

  it("puts Matured ahead of the live curve", () => {
    const { buckets } = pivotByTenor([
      cell("FX-ASIA-01", "Delta_USD", "3-5Y", 1),
      cell("FX-ASIA-01", "Delta_USD", "Matured", 12_000_000),
    ]);

    expect(buckets).toEqual(["Matured", "3-5Y"]);
  });

  it("shows only the buckets that carry something", () => {
    // A row of empty columns is noise; the desk holds nothing at 10Y+ here.
    const { buckets } = pivotByTenor([cell("A", "DV01", "3-5Y", 500)]);

    expect(buckets).toEqual(["3-5Y"]);
  });

  it("keeps a bucket the backend adds that this list has not heard of", () => {
    // Appended rather than dropped: an unknown point shows up out of order,
    // which is visible, instead of vanishing out of a total, which is not.
    const { buckets, rows } = pivotByTenor([
      cell("A", "DV01", "0-3M", 100),
      cell("A", "DV01", "30Y+", 900),
    ]);

    expect(buckets).toEqual(["0-3M", "30Y+"]);
    expect(rows[0].total).toBe(1_000);
  });

  it("gives one row per book and metric, and nets the row", () => {
    const { rows } = pivotByTenor([
      cell("RATES-ASIA-01", "DV01", "3-5Y", -1_670),
      cell("RATES-ASIA-01", "DV01", "5-10Y", 7_848),
      cell("RATES-ASIA-01", "Spread01", "3-5Y", 200),
      cell("CREDIT-ASIA-01", "DV01", "1-3Y", 1_200),
    ]);

    expect(rows).toHaveLength(3);
    const dv01 = rows.find((row) => row.book === "RATES-ASIA-01" && row.metric === "DV01");
    expect(dv01?.total).toBe(6_178);
    expect(dv01?.cells.get("5-10Y")).toBe(7_848);
  });

  it("returns an empty grid rather than throwing on no data", () => {
    expect(pivotByTenor([])).toEqual({ buckets: [], rows: [] });
  });
});

describe("isCurvePosition", () => {
  it("flags a row holding exposure on both sides of zero", () => {
    // The whole reason for the view: these two nearly cancel at book level.
    const { rows } = pivotByTenor([
      cell("A", "DV01", "1-3Y", -5_000),
      cell("A", "DV01", "5-10Y", 5_100),
    ]);

    expect(isCurvePosition(rows[0])).toBe(true);
    expect(Math.abs(rows[0].total)).toBeLessThan(200);
  });

  it("leaves a one-sided position unflagged however many points it spans", () => {
    const { rows } = pivotByTenor([
      cell("A", "DV01", "1-3Y", 5_000),
      cell("A", "DV01", "5-10Y", 3_000),
      cell("A", "DV01", "10Y+", 0),
    ]);

    expect(isCurvePosition(rows[0])).toBe(false);
  });
});

describe("nearTermShare", () => {
  it("reports the share of gross exposure inside three months", () => {
    const { rows } = pivotByTenor([
      cell("EQD-ASIA-01", "Delta_USD", "0-3M", 37_924_168),
    ]);

    expect(nearTermShare(rows[0])).toBe(1);
  });

  it("counts Matured as near-term, because it is already gone", () => {
    const { rows } = pivotByTenor([
      cell("FX-ASIA-01", "Delta_USD", "Matured", 12_000_000),
      cell("FX-ASIA-01", "Delta_USD", "0-3M", 6_610_500),
    ]);

    expect(nearTermShare(rows[0])).toBe(1);
  });

  it("measures gross, so an offsetting far leg does not hide the roll-off", () => {
    // Netting first would report this row as having no near-term exposure at
    // all, when in fact half of it disappears within the quarter.
    const { rows } = pivotByTenor([
      cell("A", "DV01", "0-3M", 5_000),
      cell("A", "DV01", "5-10Y", -5_000),
    ]);

    expect(rows[0].total).toBe(0);
    expect(nearTermShare(rows[0])).toBe(0.5);
  });

  it("is zero for a book positioned further out", () => {
    const { rows } = pivotByTenor([
      cell("RATES-ASIA-01", "DV01", "3-12M", -202),
      cell("RATES-ASIA-01", "DV01", "5-10Y", 7_848),
    ]);

    expect(nearTermShare(rows[0])).toBe(0);
  });

  it("does not divide by zero on a row of zeroes", () => {
    const { rows } = pivotByTenor([cell("A", "DV01", "0-3M", 0)]);

    expect(nearTermShare(rows[0])).toBe(0);
  });
});

describe("booksRollingOff", () => {
  it("flags a book whose every metric is near-term", () => {
    const flagged = booksRollingOff([
      cell("EQD-ASIA-01", "Delta_USD", "0-3M", 37_924_168),
      cell("EQD-ASIA-01", "Vega_USD", "0-3M", 30_395),
    ]);

    expect(flagged.has("EQD-ASIA-01")).toBe(true);
  });

  it("leaves a book alone when one of its metrics sits further out", () => {
    // Partial is not the same as whole: a book with real risk past the quarter
    // must not be labelled as rolling off it.
    const flagged = booksRollingOff([
      cell("MIXED", "Delta_USD", "0-3M", 5_000_000),
      cell("MIXED", "DV01", "5-10Y", 7_848),
    ]);

    expect(flagged.has("MIXED")).toBe(false);
  });

  it("never adds one metric to another", () => {
    // A JTD in the millions beside a DV01 in the hundreds: summed, the DV01
    // vanishes and the book is judged on the JTD alone. Counted per metric,
    // the far-dated DV01 still keeps the book off the list.
    const flagged = booksRollingOff([
      cell("CREDIT-ASIA-01", "JTD_USD", "0-3M", -14_000_000),
      cell("CREDIT-ASIA-01", "DV01", "3-5Y", 1_068),
    ]);

    expect(flagged.has("CREDIT-ASIA-01")).toBe(false);
  });

  it("returns nothing for an empty grid", () => {
    expect(booksRollingOff([]).size).toBe(0);
  });
});
