import { useState, useEffect, useCallback } from "react";
import { api } from "../api/client";
import type { TraceListResponse } from "../types";

export function useTraces(
  params: { limit?: number; offset?: number; status?: string } = {},
  pollingEnabled = true,
) {
  const [data, setData] = useState<TraceListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetchData = useCallback(async () => {
    try {
      const result = await api.getTraces(params);
      setData(result);
      setError(null);
    } catch (e) {
      setError(e as Error);
    } finally {
      setLoading(false);
    }
  }, [params.limit, params.offset, params.status]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  useEffect(() => {
    if (!pollingEnabled || !data) return;
    const hasRunning = data.traces.some((t) => t.status === "running");
    if (!hasRunning) return;

    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, [pollingEnabled, data, fetchData]);

  return { data, loading, error, refetch: fetchData };
}
