import { useState, useCallback } from "react";
import { api } from "../api/client";
import type { ReplayResult, SpanMutation } from "../types";

export function useReplay() {
  const [result, setResult] = useState<ReplayResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const replay = useCallback(
    async (traceId: string, mutations: SpanMutation[]) => {
      setLoading(true);
      setError(null);
      try {
        const res = await api.replay(traceId, mutations);
        setResult(res);
        return res;
      } catch (e) {
        setError(e as Error);
        return null;
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  return { result, loading, error, replay };
}
