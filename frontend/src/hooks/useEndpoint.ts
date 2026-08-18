/**
 * One fetch-with-state hook, shared by every view.
 *
 * Keeps loading, error and stale-result handling in one place: a view that
 * forgets any of the three shows a blank panel or, worse, the previous date's
 * numbers under a new date.
 */

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../api/client";

export interface Endpoint<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
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
        setData(null);
        setLoading(false);
      });

    return () => {
      current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, attempt]);

  return { data, error, loading, reload };
}
