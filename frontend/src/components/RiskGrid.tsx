/**
 * Sensitivities by book and metric.
 *
 * Open and settled exposure sit side by side. The risk file still publishes
 * delta for FX spots that have already paid -- on this extract more than half
 * the FX headline -- so showing only the total would overstate what the desk
 * is exposed to, and showing only the open figure would leave a risk manager
 * hunting for the difference.
 *
 * Tenors are listed separately because they cannot be added: a total duration
 * is not a quantity that exists.
 */

import type { RiskResponse } from "../api/types";
import { level, plain, signOf, usd } from "../lib/format";

export function RiskGrid({ risk }: { risk: RiskResponse }) {
  const settledTotal = risk.by_book.reduce((sum, row) => sum + row.settled_usd, 0);

  return (
    <>
      <div className="panel">
        <h2>Risk by book</h2>
        <p className="hint">
          Sensitivities in USD as of {risk.as_of}. Only additive metrics are summed.
          {settledTotal !== 0 && (
            <>
              {" "}
              <strong className="down">{usd(settledTotal)}</strong> of the published risk
              belongs to trades that have already settled and is excluded from the open
              column.
            </>
          )}
        </p>

        <table>
          <thead>
            <tr>
              <th>Book</th>
              <th>Metric</th>
              <th className="num">Open</th>
              <th className="num">Settled</th>
              <th className="num">Total published</th>
              <th className="num">Trades</th>
            </tr>
          </thead>
          <tbody>
            {risk.by_book.map((row) => (
              <tr key={`${row.book_id}/${row.risk_metric}`}>
                <td>{row.book_id}</td>
                <td>{row.risk_metric}</td>
                <td className={`num ${signOf(row.open_usd)}`}>{usd(row.open_usd)}</td>
                <td className={`num ${row.settled_usd !== 0 ? "down" : "flat"}`}>
                  {row.settled_usd === 0 ? "—" : usd(row.settled_usd)}
                </td>
                <td className="num flat">{usd(row.total_usd)}</td>
                <td className="num">{plain(row.trade_count)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="panel">
        <h2>Tenors</h2>
        <p className="hint">
          Durations are reported per trade and never totalled. Several of these figures
          are flagged in the data quality panel as impossible.
        </p>
        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th>Book</th>
                <th>Trade</th>
                <th>Instrument</th>
                <th>Metric</th>
                <th className="num">Value</th>
                <th>Unit</th>
              </tr>
            </thead>
            <tbody>
              {risk.per_trade_tenors.map((row, index) => (
                <tr key={`${String(row.trade_id)}-${index}`}>
                  <td>{String(row.book_id)}</td>
                  <td>{String(row.trade_id)}</td>
                  <td>{String(row.instrument_id)}</td>
                  <td>{String(row.risk_metric)}</td>
                  <td className="num">{level(Number(row.value))}</td>
                  <td className="flat">{String(row.unit)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </>
  );
}
