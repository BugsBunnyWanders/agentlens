import type {
  Trace,
  TraceListResponse,
  HealthResponse,
  ReplayResult,
  SpanMutation,
} from "../types";

const BASE_URL = "/api";

class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const body = await response.text();
    throw new ApiError(response.status, body);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export interface TraceListParams {
  limit?: number;
  offset?: number;
  status?: string;
}

export const api = {
  getTraces(params: TraceListParams = {}): Promise<TraceListResponse> {
    const search = new URLSearchParams();
    if (params.limit !== undefined) search.set("limit", String(params.limit));
    if (params.offset !== undefined)
      search.set("offset", String(params.offset));
    if (params.status) search.set("status", params.status);
    const qs = search.toString();
    return request<TraceListResponse>(`/traces${qs ? `?${qs}` : ""}`);
  },

  getTrace(id: string): Promise<Trace> {
    return request<Trace>(`/traces/${id}`);
  },

  getReplays(traceId: string): Promise<{ replays: Trace[] }> {
    return request<{ replays: Trace[] }>(`/traces/${traceId}/replays`);
  },

  deleteTrace(id: string): Promise<void> {
    return request<void>(`/traces/${id}`, { method: "DELETE" });
  },

  replay(traceId: string, mutations: SpanMutation[]): Promise<ReplayResult> {
    return request<ReplayResult>("/replay", {
      method: "POST",
      body: JSON.stringify({ trace_id: traceId, mutations }),
    });
  },

  health(): Promise<HealthResponse> {
    return request<HealthResponse>("/health");
  },
} as const;
