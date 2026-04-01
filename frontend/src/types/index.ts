export type SpanKind = "llm" | "tool" | "retrieval" | "chain" | "agent" | "custom";
export type TraceStatus = "running" | "completed" | "failed";
export type SpanStatus = "running" | "completed" | "failed" | "cancelled";

export interface Span {
  id: string;
  trace_id: string;
  parent_span_id: string | null;
  kind: SpanKind;
  name: string;
  started_at: string;
  ended_at: string | null;
  status: SpanStatus;
  input: unknown;
  output: unknown;
  error: string | null;
  model: string | null;
  tokens_in: number | null;
  tokens_out: number | null;
  cost_usd: number | null;
  sequence: number;
  is_mutated: boolean;
  is_stale: boolean;
  is_reexecuted: boolean;
}

export interface Trace {
  id: string;
  name: string;
  started_at: string;
  ended_at: string | null;
  status: TraceStatus;
  metadata: Record<string, unknown>;
  spans: Span[];
  total_tokens: number | null;
  total_cost_usd: number | null;
  total_duration_ms: number | null;
  parent_trace_id: string | null;
}

export type ReplayMode = "deterministic" | "live" | "hybrid";

export interface SpanMutation {
  span_id: string;
  new_output: unknown;
}

export interface ReplayRequest {
  trace_id: string;
  mutations: SpanMutation[];
  mode: ReplayMode;
}

export interface ReplayResult {
  original_trace_id: string;
  replay_trace: Trace;
  mutated_span_ids: string[];
  diverged_at_span_id: string;
  mode: ReplayMode;
}

export interface TraceListResponse {
  traces: Trace[];
  total: number;
}

export interface HealthResponse {
  status: string;
  version: string;
  traces_count: number;
}

export interface SpanNode extends Span {
  children: SpanNode[];
  depth: number;
}
