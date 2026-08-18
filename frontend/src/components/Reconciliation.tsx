/**
 * Does the desk's risk describe the desk's book?
 *
 * Coverage first, because "every trade has sensitivities" is the question a
 * risk manager asks before trusting any total on the previous screen.
 */

import type { ReconciliationResponse } from "../api/types";
import { plain } from "../lib/format";

export function Reconciliation({ recon }: { recon: ReconciliationResponse }) {
  return (
    <div className="panel">
      <h2>Blotter against risk file</h2>
      <p className="hint">
        Every trade should carry sensitivities, every sensitivity should belong to a
        trade, and the library&rsquo;s USD figures should agree with the published FX
        rates.
      </p>

      <table>
        <thead>
          <tr>
            <th>Book</th>
            <th className="num">Trades</th>
            <th className="num">With risk</th>
            <th className="num">Coverage</th>
          </tr>
        </thead>
        <tbody>
          {recon.coverage.map((row, index) => {
            const pct = Number(row.coverage_pct);
            return (
              <tr key={`${String(row.book_id)}-${index}`}>
                <td>{String(row.book_id)}</td>
                <td className="num">{plain(Number(row.trades))}</td>
                <td className="num">{plain(Number(row.with_risk))}</td>
                <td className={`num ${pct === 100 ? "up" : "down"}`}>{pct.toFixed(1)}%</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <p className="hint" style={{ marginTop: 16 }}>
        {recon.issues.length === 0
          ? "No reconciliation breaks."
          : `${recon.issues.length} break(s) — detail in the data quality panel.`}
      </p>

      {recon.issues.length > 0 && (
        <table>
          <thead>
            <tr>
              <th>Check</th>
              <th>Entity</th>
              <th>What was found</th>
            </tr>
          </thead>
          <tbody>
            {recon.issues.map((issue, index) => (
              <tr key={`${issue.code}-${index}`}>
                <td style={{ whiteSpace: "nowrap" }}>{issue.code}</td>
                <td style={{ whiteSpace: "nowrap" }}>{issue.entity_id}</td>
                <td>{issue.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
