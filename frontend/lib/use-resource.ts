"use client";

/**
 * M2 — Ortak liste/detay fetch hook'u.
 *
 * Tasarım:
 *  - fetcher değişirse yeniden çağırır (useCallback ile dış kaynak).
 *  - cancelled flag race condition önler.
 *  - error: Error (ApiError dahil) — UI tarafında message basit alınabilir.
 */
import { useCallback, useEffect, useState } from "react";

export interface UseResourceResult<T> {
  data: T | null;
  loading: boolean;
  error: Error | null;
  reload: () => void;
}

export function useResource<T>(fetcher: () => Promise<T>): UseResourceResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  const [version, setVersion] = useState(0);

  const reload = useCallback(() => setVersion((v) => v + 1), []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetcher()
      .then((d) => {
        if (!cancelled) setData(d);
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setError(e instanceof Error ? e : new Error(String(e)));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [version]);

  return { data, loading, error, reload };
}
