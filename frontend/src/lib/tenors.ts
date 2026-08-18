/**
 * Turning the flat tenor rows into a grid that can be read across.
 *
 * A risk manager reads a curve horizontally: one line per book and metric, one
 * column per point, and the shape of the position is the shape of the row. The
 * API sends one row per cell, so the pivot happens here.
 *
 * Column order is the one thing that must not be got wrong. Sorted as strings,
 * "10Y+" lands between "0-1Y" and "1-3Y" and the curve reads back to front, so
 * the order is declared rather than derived. It mirrors the backend's own
 * _TENOR_BUCKETS; a bucket the backend adds without this list knowing about it
 * is appended rather than dropped, so a new point shows up out of order instead
 * of silently vanishing from a total.
 */

import type { TenorExposure } from "../api/types";

/** Past first, then along the curve. Mirrors `_TENOR_BUCKETS` in risk.py. */
const CURVE_ORDER = ["Matured", "0-1Y", "1-3Y", "3-5Y", "5-10Y", "10Y+"];

export interface CurveRow {
  book: string;
  metric: string;
  /** Exposure per bucket, keyed by label. A bucket with no trades is absent. */
  cells: Map<string, number>;
  total: number;
}

export interface CurveGrid {
  /** Only the buckets that carry something, in curve order. */
  buckets: string[];
  rows: CurveRow[];
}

function rank(bucket: string): number {
  const index = CURVE_ORDER.indexOf(bucket);
  return index === -1 ? CURVE_ORDER.length : index;
}

export function pivotByTenor(exposures: TenorExposure[]): CurveGrid {
  const rows = new Map<string, CurveRow>();
  const seen = new Set<string>();

  for (const exposure of exposures) {
    const key = `${exposure.book_id}/${exposure.risk_metric}`;
    const row = rows.get(key) ?? {
      book: exposure.book_id,
      metric: exposure.risk_metric,
      cells: new Map<string, number>(),
      total: 0,
    };
    row.cells.set(exposure.tenor_bucket, (row.cells.get(exposure.tenor_bucket) ?? 0) + exposure.open_usd);
    row.total += exposure.open_usd;
    rows.set(key, row);
    seen.add(exposure.tenor_bucket);
  }

  const buckets = [...seen].sort((a, b) => rank(a) - rank(b) || a.localeCompare(b));

  return { buckets, rows: [...rows.values()] };
}

/**
 * Whether a row is a curve position rather than a single point.
 *
 * Worth calling out on screen: a book long one part of the curve and short
 * another can total to almost nothing while carrying real exposure to its
 * shape, which is exactly what the book-level grid hides.
 */
export function isCurvePosition(row: CurveRow): boolean {
  const values = [...row.cells.values()].filter((value) => value !== 0);
  return values.some((value) => value > 0) && values.some((value) => value < 0);
}
