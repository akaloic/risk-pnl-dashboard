/**
 * Who the desk faces, ranked by what a default would cost.
 *
 * Deliberately not ranked by notional. A ten million dollar forward against a
 * name that owes the desk nothing is ten million of business and no credit
 * risk, and a limit set on size manages the wrong number. Both columns are
 * here so the difference between them can be seen rather than argued about.
 */

import type { CounterpartyExposure } from "../api/types";
import { dominates } from "../lib/emphasis";
import { plain, signOf, usd } from "../lib/format";

export function CounterpartyGrid({ exposures }: { exposures: CounterpartyExposure[] }) {
  const isBig = dominates(exposures.map((row) => row.current_exposure_usd));
  const total = exposures.reduce((sum, row) => sum + row.current_exposure_usd, 0);
  const top = exposures[0];

  return (
    <div className="panel">
      <h2>Counterparty exposure</h2>
      <p className="hint">
        Ranked by current exposure — the marks that are in the desk&rsquo;s favour, which
        is what a default would actually cost. Notional is the size of the relationship
        and is a different ordering.
        {top && total > 0 && (
          <>
            {" "}
            <strong>{top.counterparty_name}</strong> carries{" "}
            <strong>{top.share_of_exposure_pct}%</strong> of it.
          </>
        )}
      </p>

      <table>
        <thead>
          <tr>
            <th scope="col">Counterparty</th>
            <th scope="col" className="num">Current exposure</th>
            <th scope="col" className="num">Share</th>
            <th scope="col" className="num">Net mark</th>
            <th scope="col" className="num">Gross notional</th>
            <th scope="col" className="num">Open</th>
            <th scope="col" className="num">Settled</th>
            <th scope="col" className="num">Books</th>
          </tr>
        </thead>
        <tbody>
          {exposures.map((row) => (
            <tr key={row.counterparty_id}>
              <th scope="row">
                {row.counterparty_name}
                {row.current_exposure_usd === 0 && row.gross_notional_usd > 0 && (
                  <span
                    className="tag"
                    title="Real business, but nothing is owed to the desk: a default here costs nothing"
                  >
                    no exposure
                  </span>
                )}
              </th>
              <td
                className={`num ${isBig(row.current_exposure_usd) ? "dominant up" : "flat"}`}
              >
                {row.current_exposure_usd === 0 ? "—" : usd(row.current_exposure_usd)}
              </td>
              <td className="num flat">{row.share_of_exposure_pct}%</td>
              <td className={`num ${signOf(row.net_mtm_usd)}`}>{usd(row.net_mtm_usd)}</td>
              <td className="num flat">{usd(row.gross_notional_usd)}</td>
              <td className="num">{plain(row.open_trades)}</td>
              <td className="num flat">
                {row.settled_trades === 0 ? "—" : plain(row.settled_trades)}
              </td>
              <td className="num">{plain(row.books)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
