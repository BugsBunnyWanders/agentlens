import { useState, useEffect, useCallback } from "react";
import { api } from "../api/client";
import type { Trace } from "../types";

export function useTrace(traceId: string | undefined) {
  const [trace, setTrace] = useState<Trace | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchData = useCallback(async () => {
    if (!traceId) return;
    setLoading(true);
    try {
      const result = await api.getTrace(traceId);
      setTrace(result);
      setError(null);
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
  }, [traceId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return { trace, loading, error, refetch: fetchData };
}
