import type { Span } from "../types";
import { JsonViewer } from "./JsonViewer";
import { SpanKindIcon } from "./SpanKindIcon";
import { StatusBadge } from "./StatusBadge";
import { formatDuration, formatTimestamp, formatTokens, formatCost } from "../lib/format";
import { getSpanDurationMs } from "../lib/spans";

interface SpanDetailPanelProps {
  span: Span;
  onFork: () => void;
}

export function SpanDetailPanel({ span, onFork }: SpanDetailPanelProps) {
  const durationMs = getSpanDurationMs(span);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <SpanKindIcon kind={span.kind} />
          <h3 className="text-sm font-semibold text-zinc-100">{span.name}</h3>
          <StatusBadge status={span.status} />
          {span.is_mutated && (
            <span className="text-[10px] text-blue-400 bg-blue-500/20 border border-blue-500/40 px-1.5 py-0.5 rounded font-medium">
              EDITED
            </span>
          )}
        </div>
        <button
          onClick={onFork}
          className="bg-blue-600 hover:bg-blue-500 text-white px-3 py-1.5 rounded-md text-xs font-medium transition-colors"
        >
          Fork &amp; Replay
        </button>
      </div>

      <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-xs">
        <div className="flex justify-between text-zinc-400">
          <span>Kind</span>
          <span className="text-zinc-300">{span.kind}</span>
        </div>
        <div className="flex justify-between text-zinc-400">
          <span>Duration</span>
          <span className="text-zinc-300 font-mono">{formatDuration(durationMs)}</span>
        </div>
        {span.model && (
          <div className="flex justify-between text-zinc-400">
            <span>Model</span>
            <span className="text-zinc-300">{span.model}</span>
          </div>
        )}
        {(span.tokens_in != null || span.tokens_out != null) && (
          <div className="flex justify-between text-zinc-400">
            <span>Tokens</span>
            <span className="text-zinc-300 font-mono">
              {formatTokens(span.tokens_in)} in / {formatTokens(span.tokens_out)} out
            </span>
          </div>
        )}
        {span.cost_usd != null && (
          <div className="flex justify-between text-zinc-400">
            <span>Cost</span>
            <span className="text-zinc-300 font-mono">{formatCost(span.cost_usd)}</span>
          </div>
        )}
        <div className="flex justify-between text-zinc-400">
          <span>Started</span>
          <span className="text-zinc-300 text-[11px]">{formatTimestamp(span.started_at)}</span>
        </div>
      </div>

      {span.error && (
        <div className="bg-red-900/20 border border-red-800/40 rounded-md p-3">
          <div className="text-xs font-medium text-red-400 mb-1">Error</div>
          <pre className="text-xs text-red-300 font-mono whitespace-pre-wrap">
            {span.error}
          </pre>
        </div>
      )}

      <div>
        <div className="text-xs font-medium text-zinc-400 mb-1">Input</div>
        <div className="bg-surface-0 rounded-md border border-zinc-800">
          <JsonViewer data={span.input} maxHeight="250px" />
        </div>
      </div>

      <div>
        <div className="text-xs font-medium text-zinc-400 mb-1">Output</div>
        <div className="bg-surface-0 rounded-md border border-zinc-800">
          <JsonViewer data={span.output} maxHeight="250px" />
        </div>
      </div>
    </div>
  );
}
