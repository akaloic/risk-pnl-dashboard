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

import { useMemo } from "react";
import type { RiskResponse } from "../api/types";
import { level, plain, signOf, usd } from "../lib/format";
import { isCurvePosition, nearTermShare, pivotByTenor } from "../lib/tenors";

export function RiskGrid({ risk }: { risk: RiskResponse }) {
  const settledTotal = risk.by_book.reduce((sum, row) => sum + row.settled_usd, 0);
  const curve = useMemo(() => pivotByTenor(risk.by_tenor), [risk.by_tenor]);

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
              <th scope="col">Book</th>
              <th scope="col">Metric</th>
              <th scope="col" className="num">Open</th>
              <th scope="col" className="num">Settled</th>
              <th scope="col" className="num">Total published</th>
              <th scope="col" className="num">Trades</th>
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
        <h2>Open risk along the curve</h2>
        <p className="hint">
          The same open exposure, split by years to maturity. A book total says how
          much a parallel shift is worth and nothing about where the position sits —
          and a long against a short nets to almost nothing at book level while still
          carrying the shape. Rows marked <span className="curve-flag">curve</span>{" "}
          hold exposure on both sides of zero.
        </p>

        <div className="scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Book</th>
                <th scope="col">Metric</th>
                {curve.buckets.map((bucket) => (
                  <th scope="col" className="num" key={bucket}>
                    {bucket}
                  </th>
                ))}
                <th scope="col" className="num">
                  Net
                </th>
              </tr>
            </thead>
            <tbody>
              {curve.rows.map((row) => (
                <tr key={`${row.book}/${row.metric}`}>
                  <th scope="row">{row.book}</th>
                  <td>
                    {row.metric}
                    {isCurvePosition(row) && <span className="curve-flag">curve</span>}
                    {nearTermShare(row) >= 0.5 && (
                      <span className="roll-flag">
                        rolls off · {Math.round(nearTermShare(row) * 100)}% ≤3M
                      </span>
                    )}
                  </td>
                  {curve.buckets.map((bucket) => {
                    const value = row.cells.get(bucket);
                    return (
                      <td
                        key={bucket}
                        className={`num ${value === undefined ? "flat" : signOf(value)}`}
                      >
                        {value === undefined ? "—" : usd(value)}
                      </td>
                    );
                  })}
                  <td className={`num ${signOf(row.total)}`}>{usd(row.total)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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
                <th scope="col">Book</th>
                <th scope="col">Trade</th>
                <th scope="col">Instrument</th>
                <th scope="col">Metric</th>
                <th scope="col" className="num">Value</th>
                <th scope="col">Unit</th>
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
