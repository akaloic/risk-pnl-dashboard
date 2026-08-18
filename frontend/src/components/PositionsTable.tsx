/**
 * Net positions by book and instrument.
 *
 * Quantity and notional are both shown because neither is meaningful on its
 * own across the desk: equity trades book a notional of zero and are sized in
 * contracts, while swaps and FX carry a quantity of one and only mean anything
 * in notional. Settled positions stay visible with a tag rather than being
 * filtered away -- the risk file still carries their delta, and hiding them
 * here would make that harder to explain.
 */

import { useMemo, useState } from "react";
import type { Position } from "../api/types";
import { plain, signOf } from "../lib/format";
import { Empty } from "./Loading";

type SortKey = "book_id" | "instrument_id" | "net_quantity" | "net_notional";

export function PositionsTable({ positions }: { positions: Position[] }) {
  const [sort, setSort] = useState<SortKey>("book_id");
  const [openOnly, setOpenOnly] = useState(false);

  const rows = useMemo(() => {
    const filtered = openOnly
      ? positions.filter((row) => row.position_status === "OPEN")
      : positions;

    return [...filtered].sort((a, b) => {
      const left = a[sort];
      const right = b[sort];
      if (typeof left === "number" && typeof right === "number") {
        return Math.abs(right) - Math.abs(left);
      }
      return String(left).localeCompare(String(right));
    });
  }, [positions, sort, openOnly]);

  // The control is a button inside the header rather than a click handler on
  // the cell itself: a bare onClick on a <th> cannot be reached by keyboard and
  // announces nothing, so the column would be unsortable without a mouse.
  const header = (key: SortKey, label: string, numeric = false) => (
    <th
      scope="col"
      className={numeric ? "num" : undefined}
      aria-sort={sort === key ? "descending" : "none"}
    >
      <button type="button" className="sort" onClick={() => setSort(key)}>
        {label}
        {sort === key ? " ▾" : ""}
      </button>
    </th>
  );

  return (
    <div className="panel">
      <h2>Positions</h2>
      <p className="hint">
        {plain(rows.length)} netted positions.{" "}
        <label style={{ cursor: "pointer" }}>
          <input
            type="checkbox"
            checked={openOnly}
            onChange={(event) => setOpenOnly(event.target.checked)}
          />{" "}
          open only
        </label>
      </p>

      {rows.length === 0 ? (
        <Empty>
          No positions on this date{openOnly ? " once settled trades are hidden" : ""}.
        </Empty>
      ) : (
      <div className="scroll">
        <table>
          <thead>
            <tr>
              {header("book_id", "Book")}
              {header("instrument_id", "Instrument")}
              <th scope="col">Product</th>
              <th scope="col">Ccy</th>
              {header("net_quantity", "Net qty", true)}
              <th scope="col" className="num">Gross qty</th>
              {header("net_notional", "Net notional", true)}
              <th scope="col" className="num">Trades</th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={`${row.book_id}/${row.instrument_id}/${row.product_type}/${row.position_status}`}>
                <td>{row.book_id}</td>
                <td title={row.instrument_description}>{row.instrument_id}</td>
                <td>{row.product_type}</td>
                <td>{row.currency}</td>
                <td className={`num ${signOf(row.net_quantity)}`}>{plain(row.net_quantity)}</td>
                <td className="num">{plain(row.gross_quantity)}</td>
                <td className={`num ${signOf(row.net_notional)}`}>{plain(row.net_notional)}</td>
                <td className="num">{row.trade_count}</td>
                <td>
                  {row.position_status === "SETTLED" ? (
                    <span className="tag settled">SETTLED</span>
                  ) : (
                    <span className="tag">OPEN</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      )}
    </div>
  );
}
