import { useMemo, useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { useTrace } from "../hooks/useTrace";
import { api } from "../api/client";
import type { Trace as TraceType } from "../types";
import { useKeyboardNav } from "../hooks/useKeyboardNav";
import { TraceDetailProvider, useTraceDetail } from "../context/TraceDetailContext";
import { SpanTimeline } from "./SpanTimeline";
import { SpanDetailPanel } from "./SpanDetailPanel";
import { SpanEditor } from "./SpanEditor";
import { StatusBadge } from "./StatusBadge";
import { buildSpanTree, flattenSpanTree } from "../lib/spans";
import { formatDuration, formatTokens, formatCost, formatTimestamp } from "../lib/format";

function TraceDetailInner() {
  const { traceId } = useParams<{ traceId: string }>();
  const { trace, loading, error } = useTrace(traceId);
  const {
    selectedSpanId,
    setSelectedSpanId,
    isEditorOpen,
    editorSpanId,
    openEditor,
    closeEditor,
  } = useTraceDetail();

  const spanTree = useMemo(
    () => (trace ? buildSpanTree(trace.spans) : []),
    [trace],
  );
  const flatSpans = useMemo(() => flattenSpanTree(spanTree), [spanTree]);

  useKeyboardNav({
    spans: flatSpans,
    selectedSpanId,
    setSelectedSpanId,
    openEditor,
    isEditorOpen,
  });

  const [replays, setReplays] = useState<TraceType[]>([]);

  useEffect(() => {
    if (trace && !trace.parent_trace_id) {
      api.getReplays(trace.id).then((r) => setReplays(r.replays)).catch(() => {});
    }
  }, [trace]);

  const selectedSpan = trace?.spans.find((s) => s.id === selectedSpanId) ?? null;
  const editorSpan = trace?.spans.find((s) => s.id === editorSpanId) ?? null;

  if (loading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8 text-center text-zinc-500">
        Loading...
      </div>
    );
  }

  if (error || !trace) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8 text-center text-red-400">
        {error ? `Error: ${error.message}` : "Trace not found"}
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 py-4">
      <div className="flex items-center gap-3 mb-4">
        <Link
          to="/"
          className="text-zinc-400 hover:text-zinc-200 text-sm transition-colors"
        >
          &larr; Traces
        </Link>
        <span className="text-zinc-600">/</span>
        <h1 className="text-sm font-semibold text-zinc-100">{trace.name}</h1>
        <StatusBadge status={trace.status} />
        {trace.parent_trace_id && (
          <>
            <Link
              to={`/traces/${trace.parent_trace_id}`}
              className="text-xs text-blue-400 hover:text-blue-300"
            >
              View original
            </Link>
            <Link
              to={`/traces/${trace.parent_trace_id}/replay/${trace.id}`}
              className="text-xs bg-blue-600 hover:bg-blue-500 text-white px-2.5 py-1 rounded-md font-medium transition-colors"
            >
              Compare side-by-side
            </Link>
          </>
        )}
        {!trace.parent_trace_id && replays.length > 0 && (
          <Link
            to={`/traces/${trace.id}/replay/${replays[0].id}`}
            className="text-xs bg-blue-600 hover:bg-blue-500 text-white px-2.5 py-1 rounded-md font-medium transition-colors"
          >
            Compare with replay{replays.length > 1 ? ` (${replays.length})` : ""}
          </Link>
        )}
      </div>

      <div className="flex items-center gap-6 mb-4 text-xs text-zinc-400">
        <span>Duration: <span className="text-zinc-300 font-mono">{formatDuration(trace.total_duration_ms)}</span></span>
        <span>Tokens: <span className="text-zinc-300 font-mono">{formatTokens(trace.total_tokens)}</span></span>
        <span>Cost: <span className="text-zinc-300 font-mono">{formatCost(trace.total_cost_usd)}</span></span>
        <span>Started: <span className="text-zinc-300">{formatTimestamp(trace.started_at)}</span></span>
        <span>Spans: <span className="text-zinc-300">{trace.spans.length}</span></span>
      </div>

      <div className="grid grid-cols-[360px_1fr] gap-4 min-h-[600px]">
        <div className="bg-surface-1 rounded-lg border border-zinc-800 overflow-auto">
          <div className="px-3 py-2 border-b border-zinc-800 text-xs font-medium text-zinc-500 uppercase tracking-wider">
            Span Timeline
          </div>
          <SpanTimeline
            spans={flatSpans}
            selectedSpanId={selectedSpanId}
            onSelectSpan={setSelectedSpanId}
            totalDurationMs={trace.total_duration_ms}
          />
        </div>

        <div className="bg-surface-1 rounded-lg border border-zinc-800 overflow-auto p-4">
          {selectedSpan ? (
            <SpanDetailPanel
              span={selectedSpan}
              onFork={() => openEditor(selectedSpan.id)}
            />
          ) : (
            <div className="flex items-center justify-center h-full text-zinc-500 text-sm">
              Select a span to view details
              <span className="ml-2 text-xs text-zinc-600">
                (use arrow keys or j/k)
              </span>
            </div>
          )}
        </div>
      </div>

      {editorSpan && (
        <SpanEditor
          open={isEditorOpen}
          onClose={closeEditor}
          span={editorSpan}
          allSpans={trace.spans}
          traceId={trace.id}
        />
      )}
    </div>
  );
}

export function TraceDetail() {
  return (
    <TraceDetailProvider>
      <TraceDetailInner />
    </TraceDetailProvider>
  );
}
