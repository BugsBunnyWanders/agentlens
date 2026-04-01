import { Link } from "react-router-dom";
import type { Trace } from "../types";
import { StatusBadge } from "./StatusBadge";
import { formatDuration, formatTokens, formatCost, formatRelativeTime } from "../lib/format";

export function TraceListRow({ trace }: { trace: Trace }) {
  return (
    <Link
      to={`/traces/${trace.id}`}
      className="grid grid-cols-[1fr_100px_90px_80px_80px_100px] gap-3 items-center px-4 py-2.5 hover:bg-surface-2 transition-colors border-b border-zinc-800/50"
    >
      <div className="flex items-center gap-2 min-w-0">
        <span className="font-medium text-sm text-zinc-100 truncate">
          {trace.name}
        </span>
        {trace.parent_trace_id && (
          <span className="text-xs text-blue-400 bg-blue-400/10 px-1.5 py-0.5 rounded shrink-0">
            replay
          </span>
        )}
      </div>
      <StatusBadge status={trace.status} />
      <span className="text-xs text-zinc-400 font-mono">
        {formatDuration(trace.total_duration_ms)}
      </span>
      <span className="text-xs text-zinc-400 font-mono">
        {formatTokens(trace.total_tokens)}
      </span>
      <span className="text-xs text-zinc-400 font-mono">
        {formatCost(trace.total_cost_usd)}
      </span>
      <span className="text-xs text-zinc-500 text-right">
        {formatRelativeTime(trace.started_at)}
      </span>
    </Link>
  );
}
