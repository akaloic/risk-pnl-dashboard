/** Loading and failure states, so no panel ever renders blank or stale. */

interface Props {
  loading: boolean;
  error: string | null;
  onRetry?: () => void;
  children: React.ReactNode;
}

export function Loadable({ loading, error, onRetry, children }: Props) {
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
  return <>{children}</>;
}
