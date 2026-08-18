/**
 * Loading and failure states, so no panel ever renders blank or stale.
 *
 * A refresh keeps the previous numbers on screen behind a dimmed overlay
 * rather than blanking the whole view: stepping through the month a day at a
 * time is the main way this tool is used, and a flash of empty panels on every
 * step makes it feel broken.
 */

interface Props {
  loading: boolean;
  refreshing?: boolean;
  error: string | null;
  onRetry?: () => void;
  children: React.ReactNode;
}

export function Loadable({ loading, refreshing, error, onRetry, children }: Props) {
  if (error) {
    return (
      <div className="state error">
        <div>{error}</div>
        {onRetry && (
          <button type="button" onClick={onRetry}>
            Try again
          </button>
        )}
      </div>
    );
  }

  if (loading) return <div className="state">Loading…</div>;

  return (
    <div className={refreshing ? "refreshing" : undefined}>
      {refreshing && <div className="refresh-note">Updating…</div>}
      {children}
    </div>
  );
}

/** Shown in place of a table body when a query legitimately returns nothing. */
export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="state">{children}</div>;
}
