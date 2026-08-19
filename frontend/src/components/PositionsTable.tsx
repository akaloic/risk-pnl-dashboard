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
import { type SortState, ariaSortFor, nextSort, sortRows } from "../lib/sorting";
import { Empty } from "./Loading";

// Every column the table shows is sortable. Half of them being inert taught a
// user that sorting does not work here, which is worse than not offering it.
type SortKey =
  | "book_id"
  | "instrument_id"
  | "product_type"
  | "currency"
  | "net_quantity"
  | "gross_quantity"
  | "net_notional"
  | "trade_count"
  | "position_status";

export function PositionsTable({ positions }: { positions: Position[] }) {
  const [sort, setSort] = useState<SortState<SortKey>>({
    key: "book_id",
    direction: "asc",
  });
  const [openOnly, setOpenOnly] = useState(false);

  const rows = useMemo(() => {
    const filtered = openOnly
      ? positions.filter((row) => row.position_status === "OPEN")
      : positions;

    return sortRows(filtered, sort);
  }, [positions, sort, openOnly]);

  // The control is a button inside the header rather than a click handler on
  // the cell itself: a bare onClick on a <th> cannot be reached by keyboard and
  // announces nothing, so the column would be unsortable without a mouse.
  const header = (key: SortKey, label: string, numeric = false) => (
    <th scope="col" className={numeric ? "num" : undefined} aria-sort={ariaSortFor(sort, key)}>
      <button
        type="button"
        className="sort"
        onClick={() => setSort((current) => nextSort(current, key))}
      >
        {label}
        {sort.key === key && (
          <span aria-hidden="true">{sort.direction === "desc" ? " \u25be" : " \u25b4"}</span>
        )}
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
              {header("product_type", "Product")}
              {header("currency", "Ccy")}
              {header("net_quantity", "Net qty", true)}
              {header("gross_quantity", "Gross qty", true)}
              {header("net_notional", "Net notional", true)}
              {header("trade_count", "Trades", true)}
              {header("position_status", "Status")}
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
