/**
 * The trades behind a book's P&L, biggest contributor first.
 *
 * This is what makes the headline figure arguable. A trader who sees a book
 * down 143k asks which trades did it, and the answer has to include the levels
 * the number came from -- the traded level, the mark, and the method used --
 * so the figure can be checked without opening the extracts.
 *
 * The footer ties back to the card above: if the parts do not sum to the whole,
 * one of the two screens is wrong and it should be obvious which.
 */

import { useCallback, useMemo } from "react";
import { api } from "../api/client";
import { useEndpoint } from "../hooks/useEndpoint";
import { level, signOf, usd, usdPrecise } from "../lib/format";
import { positionKey, positionsByInstrument } from "../lib/legs";
import { Loadable } from "./Loading";

interface Props {
  book: string;
  asOf: string;
  expected: number;
  onClose: () => void;
}

export function TradeDetail({ book, asOf, expected, onClose }: Props) {
  const trades = useEndpoint(
    useCallback(() => api.pnlByTrade(asOf), [asOf]),
    [asOf],
  );

  const rows = useMemo(
    () =>
      (trades.data ?? [])
        .filter((row) => row.book_id === book)
        .sort((a, b) => Math.abs(b.pnl_usd) - Math.abs(a.pnl_usd)),
    [trades.data, book],
  );

  // Which of these lines are legs of one instrument rather than positions in
  // their own right. Sorting by size puts the legs of a hedged position at the
  // top of the table looking like the two worst trades on the desk.
  const positions = useMemo(() => positionsByInstrument(rows), [rows]);

  const total = rows.reduce((sum, row) => sum + row.pnl_usd, 0);
  const tiesOut = Math.abs(total - expected) < 0.01;

  return (
    <div className="panel">
      <div className="panel-head">
        <div>
          <h2>{book} — P&amp;L by trade</h2>
          <p className="hint">
            Since inception, largest contributor first. Levels are what each figure was
            computed from. Lines marked <span className="leg-flag">leg</span> share an
            instrument with another trade and are one position, not two.
          </p>
        </div>
        <button type="button" className="close" onClick={onClose} aria-label="Close">
          ×
        </button>
      </div>

      <Loadable
        loading={trades.loading}
        refreshing={trades.refreshing}
        error={trades.error}
        onRetry={trades.reload}
      >
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Trade</th>
                <th scope="col">Instrument</th>
                <th scope="col">Method</th>
                <th scope="col" className="num">Entry</th>
                <th scope="col" className="num">Mark</th>
                <th scope="col" className="num">P&amp;L (local)</th>
                <th scope="col">Ccy</th>
                <th scope="col" className="num">P&amp;L (USD)</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.trade_id}>
                  <td>{row.trade_id}</td>
                  <td>
                    {row.instrument_id}
                    {(positions.get(positionKey(row))?.tradeIds.length ?? 0) > 1 && (
                      <span
                        className="leg-flag"
                        title={`${positions.get(positionKey(row))?.tradeIds.join(" + ")} are one position on this instrument`}
                      >
                        leg · net {usd(positions.get(positionKey(row))?.net ?? 0)}
                      </span>
                    )}
                  </td>
                  <td className="flat">{row.method}</td>
                  <td className="num">{level(row.reference_level)}</td>
                  <td className="num">{level(row.current_level)}</td>
                  <td className={`num ${signOf(row.pnl_ccy)}`}>{level(row.pnl_ccy)}</td>
                  <td className="flat">{row.pnl_currency}</td>
                  <td className={`num ${signOf(row.pnl_usd)}`}>{usdPrecise(row.pnl_usd)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td colSpan={7}>
                  {rows.length} trades
                  {!tiesOut && (
                    <span className="down"> — does not tie to the book total</span>
                  )}
                </td>
                <td className={`num ${signOf(total)}`}>{usd(total)}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </Loadable>
    </div>
  );
}
