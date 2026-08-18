/**
 * One fetch-with-state hook, shared by every view.
 *
 * Keeps loading, error and stale-reply handling in one place: a view that
 * forgets any of the three shows a blank panel or, worse, the previous date's
 * numbers under a new date.
 */

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../api/client";

export interface Endpoint<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  /** True while refreshing with a previous result still on screen. */
  refreshing: boolean;
  reload: () => void;
}

export function useEndpoint<T>(fetcher: () => Promise<T>, deps: unknown[]): Endpoint<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);

  useEffect(() => {
    // A reply that arrives after the date changed again must not overwrite the
    // newer one; the flag drops it instead.
    let current = true;
    setLoading(true);
    setError(null);

    fetcher()
      .then((result) => {
        if (!current) return;
        setData(result);
        setLoading(false);
      })
      .catch((caught: unknown) => {
        if (!current) return;
        setError(caught instanceof ApiError ? caught.message : String(caught));
        // The previous result is dropped on failure: leaving it on screen under
        // a new as-of date would show one day's numbers labelled as another's.
        setData(null);
        setLoading(false);
      });

    return () => {
      current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, attempt]);

  return {
    data,
    error,
    loading: loading && data === null,
    refreshing: loading && data !== null,
    reload,
  };
}
