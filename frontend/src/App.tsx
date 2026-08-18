import { useCallback, useState } from "react";
import { api } from "./api/client";
import { DataQualityPanel } from "./components/DataQualityPanel";
import { DeskSummary } from "./components/DeskSummary";
import { Loadable } from "./components/Loading";
import { PnlChart } from "./components/PnlChart";
import { PositionsTable } from "./components/PositionsTable";
import { Reconciliation } from "./components/Reconciliation";
import { RiskGrid } from "./components/RiskGrid";
import { useEndpoint } from "./hooks/useEndpoint";

const DEFAULT_AS_OF = "2026-08-05";

type Tab = "summary" | "positions" | "risk" | "quality";

const TABS: { id: Tab; label: string }[] = [
  { id: "summary", label: "Desk summary" },
  { id: "positions", label: "Positions" },
  { id: "risk", label: "Risk" },
  { id: "quality", label: "Data quality" },
];

export default function App() {
  const [asOf, setAsOf] = useState(DEFAULT_AS_OF);
  const [tab, setTab] = useState<Tab>("summary");
  const [book, setBook] = useState<string | null>(null);

  const health = useEndpoint(() => api.health(), []);
  const pnl = useEndpoint(useCallback(() => api.pnl(asOf), [asOf]), [asOf]);
  const positions = useEndpoint(useCallback(() => api.positions(asOf), [asOf]), [asOf]);
  const risk = useEndpoint(useCallback(() => api.risk(asOf), [asOf]), [asOf]);
  const quality = useEndpoint(useCallback(() => api.dataQuality(asOf), [asOf]), [asOf]);
  const recon = useEndpoint(useCallback(() => api.reconciliation(asOf), [asOf]), [asOf]);

  const errorCount = quality.data?.counts.ERROR ?? 0;

  return (
    <>
      <header className="app-header">
        <div>
          <h1>Risk &amp; P&amp;L &mdash; Asia cross-asset desk</h1>
          <div className="sub">
            Rates, credit, FX and equity derivatives
            {health.data &&
              ` · ${health.data.trades} trades · reporting in ${health.data.reporting_currency}`}
          </div>
        </div>
        <label className="as-of">
          As of
          <input
            type="date"
            value={asOf}
            min={health.data?.first_business_day}
            max={health.data?.last_business_day}
            onChange={(event) => setAsOf(event.target.value)}
          />
        </label>
      </header>

      <nav className="tabs">
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            type="button"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
          >
            {label}
            {id === "quality" && errorCount > 0 && (
              <span className="badge">{errorCount}</span>
            )}
          </button>
        ))}
      </nav>

      {tab === "summary" && (
        <Loadable
          loading={pnl.loading}
          refreshing={pnl.refreshing}
          error={pnl.error}
          onRetry={pnl.reload}
        >
          {pnl.data && (
            <>
              <DeskSummary pnl={pnl.data} />
              <div className="panel">
                <h2>Daily P&amp;L</h2>
                <p className="hint">
                  Bars are each day&rsquo;s move, the line is the running total.{" "}
                  <select
                    value={book ?? ""}
                    onChange={(event) => setBook(event.target.value || null)}
                  >
                    <option value="">All books</option>
                    {pnl.data.by_book.map((entry) => (
                      <option key={entry.book_id} value={entry.book_id}>
                        {entry.book_id}
                      </option>
                    ))}
                  </select>
                </p>
                <PnlChart series={pnl.data.series} book={book} />
              </div>
            </>
          )}
        </Loadable>
      )}

      {tab === "positions" && (
        <Loadable
          loading={positions.loading}
          refreshing={positions.refreshing}
          error={positions.error}
          onRetry={positions.reload}
        >
          {positions.data && <PositionsTable positions={positions.data} />}
        </Loadable>
      )}

      {tab === "risk" && (
        <Loadable
          loading={risk.loading}
          refreshing={risk.refreshing}
          error={risk.error}
          onRetry={risk.reload}
        >
          {risk.data && <RiskGrid risk={risk.data} />}
        </Loadable>
      )}

      {tab === "quality" && (
        <>
          <Loadable
            loading={quality.loading}
            refreshing={quality.refreshing}
            error={quality.error}
            onRetry={quality.reload}
          >
            {quality.data && <DataQualityPanel quality={quality.data} />}
          </Loadable>
          <Loadable
            loading={recon.loading}
            refreshing={recon.refreshing}
            error={recon.error}
            onRetry={recon.reload}
          >
            {recon.data && <Reconciliation recon={recon.data} />}
          </Loadable>
        </>
      )}
    </>
  );
}
