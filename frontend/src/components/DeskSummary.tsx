/**
 * The morning screen: where each book stands, and what moved overnight.
 *
 * The day figure leads because that is the question asked first; the position
 * since inception sits under it for context.
 */

import type { BookSummary, PnLResponse } from "../api/types";
import { plain, signOf, usd } from "../lib/format";

function Card({ title, day, inception, footer }: {
  title: string;
  day: number;
  inception: number;
  footer?: React.ReactNode;
}) {
  return (
    <div className="card">
      <h3>{title}</h3>
      <div className={`headline ${signOf(day)}`}>{usd(day)}</div>
      <div className="label">P&amp;L today</div>
      <div className="row">
        <span>Since inception</span>
        <span className={`num ${signOf(inception)}`}>{usd(inception)}</span>
      </div>
      {footer}
    </div>
  );
}

export function DeskSummary({ pnl }: { pnl: PnLResponse }) {
  return (
    <div className="cards">
      <div className="card total">
        <h3>DESK TOTAL</h3>
        <div className={`headline ${signOf(pnl.total_day_usd)}`}>
          {usd(pnl.total_day_usd)}
        </div>
        <div className="label">P&amp;L today &middot; {pnl.reporting_currency}</div>
        <div className="row">
          <span>Since inception</span>
          <span className={`num ${signOf(pnl.total_inception_usd)}`}>
            {usd(pnl.total_inception_usd)}
          </span>
        </div>
      </div>

      {pnl.by_book.map((book: BookSummary) => (
        <Card
          key={book.book_id}
          title={book.book_id}
          day={book.day_usd}
          inception={book.inception_usd}
          footer={
            <div className="row">
              <span>{plain(book.trade_count)} trades</span>
              <span>{plain(book.open_positions)} open positions</span>
            </div>
          }
        />
      ))}
    </div>
  );
}
