/**
 * Collapsing the P&L series to one figure per day.
 *
 * The API returns one row per book per day, because that is what lets the chart
 * be filtered to a single book without a second request. The chart draws one
 * bar per day, so something has to add the books up, and that step is worth
 * keeping out of the component: a bar that is short by one book still looks
 * like a perfectly plausible bar.
 */

import type { DailyPnL } from "../api/types";

export interface Day {
  date: string;
  daily: number;
  cumulative: number;
}

/** Sum every book into one row per date, oldest first. */
export function totalsByDate(series: DailyPnL[]): Day[] {
  const byDate = new Map<string, Day>();
  for (const row of series) {
    const day = byDate.get(row.date) ?? { date: row.date, daily: 0, cumulative: 0 };
    day.daily += row.daily_usd;
    day.cumulative += row.cumulative_usd;
    byDate.set(row.date, day);
  }
  return [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));
}
