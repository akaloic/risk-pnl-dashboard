import { useCallback, useState } from "react";
import { api } from "./api/client";
import { DeskSummary } from "./components/DeskSummary";
import { Loadable } from "./components/Loading";
import { useEndpoint } from "./hooks/useEndpoint";

const DEFAULT_AS_OF = "2026-08-05";

export default function App() {
  const [asOf, setAsOf] = useState(DEFAULT_AS_OF);

  const health = useEndpoint(() => api.health(), []);
  const pnl = useEndpoint(useCallback(() => api.pnl(asOf), [asOf]), [asOf]);

  return (
    <>
      <header className="app-header">
        <div>
          <h1>Risk &amp; P&amp;L &mdash; Asia cross-asset desk</h1>
          <div className="sub">
            Rates, credit, FX and equity derivatives
            {health.data && ` · ${health.data.trades} trades · reporting in ${health.data.reporting_currency}`}
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

      <Loadable loading={pnl.loading} error={pnl.error} onRetry={pnl.reload}>
        {pnl.data && <DeskSummary pnl={pnl.data} />}
      </Loadable>
    </>
  );
}
