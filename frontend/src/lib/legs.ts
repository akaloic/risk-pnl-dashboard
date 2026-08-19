/**
 * Trades that are really one position.
 *
 * The trade table sorts by size, so a book's two largest lines can be the two
 * halves of a single instrument and nothing on screen says so. On this desk
 * that is not hypothetical: the biggest daily move is TRD-034 at -205,558 and
 * the second biggest is TRD-039 at +102,692, both Nikkei September futures in
 * EQD-ASIA-01. Read as separate lines a trader concludes the worst position on
 * the desk lost 205k. Netted, it lost 103k, and the number they were about to
 * act on was twice the real one.
 *
 * The positions engine already nets these correctly. This does not re-derive
 * that -- it only marks, in the P&L view, which lines belong to the same
 * instrument so the reader knows a figure is a leg rather than a position.
 */

import type { TradePnL } from "../api/types";

export interface Position {
  /** Every trade in this book on the same instrument, biggest leg first. */
  tradeIds: string[];
  net: number;
}

/**
 * Group an already book-filtered set of trades by the instrument they are on.
 *
 * Keyed on instrument and product type together, matching how the positions
 * engine keys a position: an FX spot and an FX forward on USDJPY are two
 * positions, not one, because they close on different dates.
 */
export function positionsByInstrument(rows: TradePnL[]): Map<string, Position> {
  const groups = new Map<string, Position>();

  for (const row of rows) {
    const key = `${row.instrument_id}/${row.product_type}`;
    const group = groups.get(key) ?? { tradeIds: [], net: 0 };
    group.tradeIds.push(row.trade_id);
    group.net += row.pnl_usd;
    groups.set(key, group);
  }

  return groups;
}

/** The key a row is grouped under, so a component can look its position up. */
export function positionKey(row: TradePnL): string {
  return `${row.instrument_id}/${row.product_type}`;
}
