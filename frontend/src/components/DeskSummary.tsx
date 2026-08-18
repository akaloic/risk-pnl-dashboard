/**
 * The morning screen: where each book stands, and what moved overnight.
 *
 * The day figure leads because that is the question asked first; the position
 * since inception sits under it for context. Book cards are buttons: the next
 * question after "how much" is always "from what", and the answer is one click
 * away rather than in another tool.
 */

import type { BookSummary, PnLResponse } from "../api/types";
import { plain, signOf, usd } from "../lib/format";

interface Props {
  pnl: PnLResponse;
  selected: string | null;
  onSelect: (book: string | null) => void;
}

export function DeskSummary({ pnl, selected, onSelect }: Props) {
  return (
    <div className="cards">
      <div className="card total">
        <h3>DESK TOTAL</h3>
        <div className={`headline ${signOf(pnl.total_day_usd)}`}>{usd(pnl.total_day_usd)}</div>
        <div className="label">P&amp;L today &middot; {pnl.reporting_currency}</div>
        <div className="row">
          <span>Since inception</span>
          <span className={`num ${signOf(pnl.total_inception_usd)}`}>
            {usd(pnl.total_inception_usd)}
          </span>
        </div>
      </div>

      {pnl.by_book.map((book: BookSummary) => (
        <button
          key={book.book_id}
          type="button"
          className={`card clickable${selected === book.book_id ? " selected" : ""}`}
          onClick={() => onSelect(selected === book.book_id ? null : book.book_id)}
          aria-expanded={selected === book.book_id}
        >
          <h3>{book.book_id}</h3>
          <div className={`headline ${signOf(book.day_usd)}`}>{usd(book.day_usd)}</div>
          <div className="label">P&amp;L today</div>
          <div className="row">
            <span>Since inception</span>
            <span className={`num ${signOf(book.inception_usd)}`}>
              {usd(book.inception_usd)}
            </span>
          </div>
          <div className="row">
            <span>{plain(book.trade_count)} trades</span>
            <span>{plain(book.open_positions)} open positions</span>
          </div>
          <div className="drill">
            {selected === book.book_id ? "Hide trades" : "Show trades →"}
          </div>
        </button>
      ))}
    </div>
  );
}
