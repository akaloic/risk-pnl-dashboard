import { type KeyboardEvent, useCallback, useRef, useState } from "react";
import { api } from "./api/client";
import { CounterpartyGrid } from "./components/CounterpartyGrid";
import { DataQualityPanel } from "./components/DataQualityPanel";
import { DeskSummary } from "./components/DeskSummary";
import { Loadable } from "./components/Loading";
import { PnlChart } from "./components/PnlChart";
import { PositionsTable } from "./components/PositionsTable";
import { TradeDetail } from "./components/TradeDetail";
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
  const [drill, setDrill] = useState<string | null>(null);

  const health = useEndpoint(() => api.health(), []);
  const pnl = useEndpoint(useCallback(() => api.pnl(asOf), [asOf]), [asOf]);
  const positions = useEndpoint(useCallback(() => api.positions(asOf), [asOf]), [asOf]);
  const risk = useEndpoint(useCallback(() => api.risk(asOf), [asOf]), [asOf]);
  const counterparty = useEndpoint(useCallback(() => api.counterparty(asOf), [asOf]), [asOf]);
  const quality = useEndpoint(useCallback(() => api.dataQuality(asOf), [asOf]), [asOf]);
  const recon = useEndpoint(useCallback(() => api.reconciliation(asOf), [asOf]), [asOf]);

  const errorCount = quality.data?.counts.ERROR ?? 0;

  const tabRefs = useRef<(HTMLButtonElement | null)[]>([]);

  /** Arrows move between tabs and wrap; Home and End jump to the ends. */
  const onTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const moves: Record<string, number> = {
      ArrowRight: index + 1,
      ArrowLeft: index - 1,
      Home: 0,
      End: TABS.length - 1,
    };
    const target = moves[event.key];
    if (target === undefined) return;

    event.preventDefault();
    const next = (target + TABS.length) % TABS.length;
    setTab(TABS[next].id);
    tabRefs.current[next]?.focus();
  };

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
            onChange={(event) => {
              setAsOf(event.target.value);
              setDrill(null);
            }}
          />
        </label>
      </header>

      {/* The full tab pattern, not buttons wearing aria-selected: that attribute is
          only valid on a handful of roles, and on a plain button a screen reader is
          entitled to ignore it. Roving tabindex and arrow keys come with the pattern
          -- Tab moves past the whole strip, arrows move within it. */}
      <div className="tabs" role="tablist" aria-label="Desk views">
        {TABS.map(({ id, label }, index) => (
          <button
            key={id}
            type="button"
            role="tab"
            id={`tab-${id}`}
            aria-controls={`panel-${id}`}
            aria-selected={tab === id}
            tabIndex={tab === id ? 0 : -1}
            ref={(node) => {
              tabRefs.current[index] = node;
            }}
            onClick={() => setTab(id)}
            onKeyDown={(event) => onTabKeyDown(event, index)}
          >
            {label}
            {id === "quality" && errorCount > 0 && (
              <span className="badge">{errorCount}</span>
            )}
          </button>
        ))}
      </div>

      {tab === "summary" && (
        <div role="tabpanel" id="panel-summary" aria-labelledby="tab-summary">
        <Loadable
          loading={pnl.loading}
          refreshing={pnl.refreshing}
          error={pnl.error}
          onRetry={pnl.reload}
        >
          {pnl.data && (
            <>
              <DeskSummary
                pnl={pnl.data}
                tenors={risk.data?.by_tenor}
                selected={drill}
                onSelect={setDrill}
              />
              {drill && (
                <TradeDetail
                  book={drill}
                  asOf={asOf}
                  expected={
                    pnl.data.by_book.find((entry) => entry.book_id === drill)
                      ?.inception_usd ?? 0
                  }
                  onClose={() => setDrill(null)}
                />
              )}
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
        </div>
      )}

      {tab === "positions" && (
        <div role="tabpanel" id="panel-positions" aria-labelledby="tab-positions">
        <Loadable
          loading={positions.loading}
          refreshing={positions.refreshing}
          error={positions.error}
          onRetry={positions.reload}
        >
          {positions.data && <PositionsTable positions={positions.data} />}
        </Loadable>
        </div>
      )}

      {tab === "risk" && (
        <div role="tabpanel" id="panel-risk" aria-labelledby="tab-risk">
        <Loadable
          loading={risk.loading}
          refreshing={risk.refreshing}
          error={risk.error}
          onRetry={risk.reload}
        >
          {risk.data && <RiskGrid risk={risk.data} />}
          </Loadable>
          <Loadable
            loading={counterparty.loading}
            refreshing={counterparty.refreshing}
            error={counterparty.error}
            onRetry={counterparty.reload}
          >
            {counterparty.data && <CounterpartyGrid exposures={counterparty.data} />}
          </Loadable>
        </div>
      )}

      {tab === "quality" && (
        <div role="tabpanel" id="panel-quality" aria-labelledby="tab-quality">
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
        </div>
      )}
    </>
  );
}
