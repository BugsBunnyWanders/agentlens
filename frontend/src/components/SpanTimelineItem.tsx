import type { SpanNode } from "../types";
import { SpanKindIcon } from "./SpanKindIcon";
import { StatusBadge } from "./StatusBadge";
import { DurationBar } from "./DurationBar";
import { formatDuration, formatTokens, formatCost } from "../lib/format";
import { getSpanDurationMs } from "../lib/spans";

interface SpanTimelineItemProps {
  span: SpanNode;
  isSelected: boolean;
  totalDurationMs: number | null;
  onClick: () => void;
}

export function SpanTimelineItem({
  span,
  isSelected,
  totalDurationMs,
  onClick,
}: SpanTimelineItemProps) {
  const durationMs = getSpanDurationMs(span);

  return (
    <button
      onClick={onClick}
      className={`w-full text-left px-3 py-2 transition-colors border-l-2 ${
        isSelected
          ? "bg-surface-3 border-blue-500"
          : "border-transparent hover:bg-surface-2"
      } ${span.is_mutated ? "bg-blue-900/20" : ""}`}
      style={{ paddingLeft: `${span.depth * 20 + 12}px` }}
    >
      <div className="flex items-center gap-2">
        <SpanKindIcon kind={span.kind} />
        <span className="text-sm font-medium text-zinc-200 truncate flex-1">
          {span.name}
        </span>
        {span.is_mutated && (
          <span className="text-[10px] text-blue-400 bg-blue-500/20 border border-blue-500/40 px-1.5 py-0.5 rounded font-medium">
            EDITED
          </span>
        )}
        <StatusBadge status={span.status} />
      </div>
      <div className="flex items-center gap-3 mt-1 text-xs text-zinc-500">
        <span className="font-mono">{formatDuration(durationMs)}</span>
        <DurationBar durationMs={durationMs} totalMs={totalDurationMs} />
        {span.kind === "llm" && (
          <>
            {span.model && <span>{span.model}</span>}
            <span className="font-mono">
              {formatTokens(
                span.tokens_in != null && span.tokens_out != null
                  ? span.tokens_in + span.tokens_out
                  : null,
              )}
            </span>
            <span className="font-mono">{formatCost(span.cost_usd)}</span>
          </>
        )}
      </div>
    </button>
  );
}
