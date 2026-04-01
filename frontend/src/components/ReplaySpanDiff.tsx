import type { Span } from "../types";
import { SpanKindIcon } from "./SpanKindIcon";
import { formatDuration } from "../lib/format";
import { getSpanDurationMs } from "../lib/spans";

interface ReplaySpanDiffProps {
  originalSpan: Span;
  replaySpan: Span;
  isSelected: boolean;
  onClick: () => void;
}

function hasOutputChanged(a: Span, b: Span): boolean {
  return JSON.stringify(a.output) !== JSON.stringify(b.output);
}

export function ReplaySpanDiff({
  originalSpan,
  replaySpan,
  isSelected,
  onClick,
}: ReplaySpanDiffProps) {
  const changed = hasOutputChanged(originalSpan, replaySpan);
  const mutated = replaySpan.is_mutated;
  const stale = replaySpan.is_stale;
  const reexecuted = replaySpan.is_reexecuted;

  let bgClass = "";
  let borderClass = "border-transparent";
  if (isSelected) {
    bgClass = "bg-surface-3";
    borderClass = "border-blue-500";
  } else if (mutated) {
    bgClass = "bg-blue-900/20";
    borderClass = "border-blue-500";
  } else if (reexecuted && changed) {
    bgClass = "bg-green-900/15";
    borderClass = "border-green-500";
  } else if (reexecuted) {
    bgClass = "bg-green-900/10";
    borderClass = "border-green-500/50";
  } else if (stale) {
    bgClass = "bg-amber-900/10";
    borderClass = "border-amber-500/50";
  } else if (changed) {
    bgClass = "bg-amber-900/20";
    borderClass = "border-amber-500";
  }

  return (
    <button
      onClick={onClick}
      className={`w-full text-left grid grid-cols-2 gap-4 px-3 py-2 transition-colors border-l-2 ${borderClass} ${bgClass} hover:bg-surface-2`}
    >
      <div className="flex items-center gap-2 min-w-0">
        <SpanKindIcon kind={originalSpan.kind} />
        <span className="text-sm text-zinc-300 truncate">{originalSpan.name}</span>
        <span className="text-xs text-zinc-500 font-mono ml-auto">
          {formatDuration(getSpanDurationMs(originalSpan))}
        </span>
      </div>
      <div className="flex items-center gap-2 min-w-0">
        <SpanKindIcon kind={replaySpan.kind} />
        <span className={`text-sm truncate ${stale ? "text-zinc-500" : "text-zinc-300"}`}>
          {replaySpan.name}
        </span>
        {mutated && (
          <span className="text-[10px] text-blue-400 bg-blue-500/20 border border-blue-500/40 px-1.5 py-0.5 rounded font-medium shrink-0">
            EDITED
          </span>
        )}
        {reexecuted && (
          <span className="text-[10px] text-green-400 bg-green-500/10 border border-green-500/30 px-1.5 py-0.5 rounded font-medium shrink-0">
            RE-EXECUTED
          </span>
        )}
        {stale && !reexecuted && (
          <span className="text-[10px] text-amber-400 bg-amber-500/10 border border-amber-500/30 px-1.5 py-0.5 rounded font-medium shrink-0">
            NEEDS RE-RUN
          </span>
        )}
        {changed && !mutated && !stale && !reexecuted && (
          <span className="text-[10px] text-amber-400 bg-amber-500/20 border border-amber-500/40 px-1.5 py-0.5 rounded font-medium shrink-0">
            CHANGED
          </span>
        )}
        <span className="text-xs text-zinc-500 font-mono ml-auto">
          {formatDuration(getSpanDurationMs(replaySpan))}
        </span>
      </div>
    </button>
  );
}
