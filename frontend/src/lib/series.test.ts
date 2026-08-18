/**
 * The chart is fed one row per book per day and draws one bar per day, so the
 * aggregation in between is where a desk total can quietly go wrong. A bar that
 * is short by one book still looks like a plausible bar.
 */

import { describe, expect, it } from "vitest";
import type { DailyPnL } from "../api/types";
import { totalsByDate } from "./series";

const row = (date: string, book: string, daily: number, cumulative: number): DailyPnL => ({
  date,
  book_id: book,
  daily_usd: daily,
  cumulative_usd: cumulative,
});

describe("totalsByDate", () => {
  it("adds every book into one figure per day", () => {
    const totals = totalsByDate([
      row("2026-08-04", "RATES-ASIA-01", 100, 1_000),
      row("2026-08-04", "FX-ASIA-01", -40, -400),
      row("2026-08-05", "RATES-ASIA-01", 25, 1_025),
      row("2026-08-05", "FX-ASIA-01", -10, -410),
    ]);

    expect(totals).toEqual([
      { date: "2026-08-04", daily: 60, cumulative: 600 },
      { date: "2026-08-05", daily: 15, cumulative: 615 },
    ]);
  });

  it("orders by date whatever order the API returned", () => {
    // The series is grouped by book server-side, so the rows arrive
    // interleaved rather than chronologically.
    const totals = totalsByDate([
      row("2026-08-05", "RATES-ASIA-01", 1, 3),
      row("2026-08-03", "RATES-ASIA-01", 1, 1),
      row("2026-08-04", "RATES-ASIA-01", 1, 2),
    ]);

    expect(totals.map((day) => day.date)).toEqual([
      "2026-08-03",
      "2026-08-04",
      "2026-08-05",
    ]);
  });

  it("keeps a day whose books cancel out", () => {
    // Dropping a zero day would shorten the axis and shift every later bar.
    const totals = totalsByDate([
      row("2026-08-04", "RATES-ASIA-01", 500, 500),
      row("2026-08-04", "FX-ASIA-01", -500, -500),
    ]);

    expect(totals).toHaveLength(1);
    expect(totals[0]).toEqual({ date: "2026-08-04", daily: 0, cumulative: 0 });
  });

  it("returns nothing for an empty series rather than throwing", () => {
    expect(totalsByDate([])).toEqual([]);
  });

  it("does not mutate the rows it was handed", () => {
    // The same series is re-aggregated on every book filter change; mutating
    // it would make the second render disagree with the first.
    const series = [row("2026-08-04", "RATES-ASIA-01", 100, 1_000)];
    const before = structuredClone(series);

    totalsByDate(series);

    expect(series).toEqual(before);
  });
});
