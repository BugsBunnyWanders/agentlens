import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useTrace } from "../hooks/useTrace";
import { ReplaySpanDiff } from "./ReplaySpanDiff";
import { JsonViewer } from "./JsonViewer";
import { StatusBadge } from "./StatusBadge";

export function ReplayView() {
  const { traceId, replayId } = useParams<{
    traceId: string;
    replayId: string;
  }>();
  const { trace: original, loading: l1 } = useTrace(traceId);
  const { trace: replay, loading: l2 } = useTrace(replayId);
  const [selectedSeq, setSelectedSeq] = useState<number | null>(null);

  if (l1 || l2) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8 text-center text-zinc-500">
        Loading...
      </div>
    );
  }

  if (!original || !replay) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8 text-center text-red-400">
        Trace not found
      </div>
    );
  }

  const originalSpans = [...original.spans].sort((a, b) => a.sequence - b.sequence);
  const replaySpans = [...replay.spans].sort((a, b) => a.sequence - b.sequence);

  const hasStaleSpans = replaySpans.some((s) => s.is_stale);
  const hasReexecuted = replaySpans.some((s) => s.is_reexecuted);
  const replayMode = (replay?.metadata as Record<string, unknown>)?.replay_mode as string | undefined;

  const selectedOriginal = selectedSeq != null
    ? originalSpans.find((s) => s.sequence === selectedSeq)
    : null;
  const selectedReplay = selectedSeq != null
    ? replaySpans.find((s) => s.sequence === selectedSeq)
    : null;

  return (
    <div className="max-w-7xl mx-auto px-4 py-4">
      <div className="flex items-center gap-3 mb-4">
        <Link
          to={`/traces/${traceId}`}
          className="text-zinc-400 hover:text-zinc-200 text-sm transition-colors"
        >
          &larr; Back to trace
        </Link>
        <span className="text-zinc-600">/</span>
        <h1 className="text-sm font-semibold text-zinc-100">
          Replay Comparison
        </h1>
      </div>

      {hasReexecuted && (
        <div className="bg-green-900/15 border border-green-700/30 rounded-lg px-4 py-3 mb-4 flex items-start gap-3">
          <span className="text-green-400 text-lg leading-none mt-0.5">&#9889;</span>
          <div>
            <div className="text-sm font-medium text-green-300">
              {replayMode === "hybrid" ? "Hybrid" : "Live"} Replay
            </div>
            <div className="text-xs text-green-400/80 mt-0.5">
              Downstream spans marked
              <span className="mx-1 text-[10px] text-green-400 bg-green-500/10 border border-green-500/30 px-1.5 py-0.5 rounded font-medium">RE-EXECUTED</span>
              were actually re-run with real {replayMode === "hybrid" ? "LLM" : "API"} calls. Their output reflects the mutated input.
            </div>
          </div>
        </div>
      )}
      {hasStaleSpans && !hasReexecuted && (
        <div className="bg-amber-900/15 border border-amber-700/30 rounded-lg px-4 py-3 mb-4 flex items-start gap-3">
          <span className="text-amber-400 text-lg leading-none mt-0.5">&#9888;</span>
          <div>
            <div className="text-sm font-medium text-amber-300">Deterministic Replay</div>
            <div className="text-xs text-amber-400/80 mt-0.5">
              Only the edited span's output was changed. Downstream spans marked
              <span className="mx-1 text-[10px] text-amber-400 bg-amber-500/10 border border-amber-500/30 px-1.5 py-0.5 rounded font-medium">NEEDS RE-RUN</span>
              show their <strong>original recorded output</strong>. Use Live or Hybrid mode to re-execute them.
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-2 gap-4 mb-4">
        <div className="bg-surface-1 rounded-lg border border-zinc-800 px-4 py-2 flex items-center gap-2">
          <span className="text-xs font-medium text-zinc-400">ORIGINAL</span>
          <span className="text-sm text-zinc-200">{original.name}</span>
          <StatusBadge status={original.status} />
        </div>
        <div className="bg-surface-1 rounded-lg border border-zinc-800 px-4 py-2 flex items-center gap-2">
          <span className="text-xs font-medium text-blue-400">REPLAY</span>
          <span className="text-sm text-zinc-200">{replay.name}</span>
          <StatusBadge status={replay.status} />
        </div>
      </div>

      <div className="bg-surface-1 rounded-lg border border-zinc-800 overflow-hidden mb-4">
        <div className="grid grid-cols-2 gap-4 px-3 py-2 border-b border-zinc-800 text-xs font-medium text-zinc-500 uppercase tracking-wider">
          <span>Original Spans</span>
          <span>Replay Spans</span>
        </div>
        <div className="divide-y divide-zinc-800/50">
          {originalSpans.map((oSpan, i) => {
            const rSpan = replaySpans[i];
            if (!rSpan) return null;
            return (
              <ReplaySpanDiff
                key={oSpan.id}
                originalSpan={oSpan}
                replaySpan={rSpan}
                isSelected={selectedSeq === oSpan.sequence}
                onClick={() => setSelectedSeq(oSpan.sequence)}
              />
            );
          })}
        </div>
      </div>

      {selectedOriginal && selectedReplay && (
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-surface-1 rounded-lg border border-zinc-800 p-4">
            <div className="text-xs font-medium text-zinc-400 mb-2">
              Original Output &mdash; {selectedOriginal.name}
            </div>
            <div className="bg-surface-0 rounded-md border border-zinc-800">
              <JsonViewer data={selectedOriginal.output} maxHeight="300px" />
            </div>
          </div>
          <div className="bg-surface-1 rounded-lg border border-zinc-800 p-4">
            <div className="text-xs font-medium text-zinc-400 mb-2">
              Replay Output &mdash; {selectedReplay.name}
              {selectedReplay.is_mutated && (
                <span className="ml-2 text-blue-400 bg-blue-500/20 border border-blue-500/40 px-1.5 py-0.5 rounded text-[10px] font-medium">
                  EDITED
                </span>
              )}
              {selectedReplay.is_reexecuted && (
                <span className="ml-2 text-green-400 bg-green-500/10 border border-green-500/30 px-1.5 py-0.5 rounded text-[10px] font-medium">
                  RE-EXECUTED
                </span>
              )}
              {selectedReplay.is_stale && !selectedReplay.is_reexecuted && (
                <span className="ml-2 text-amber-400 bg-amber-500/10 border border-amber-500/30 px-1.5 py-0.5 rounded text-[10px] font-medium">
                  STALE &mdash; same as original
                </span>
              )}
            </div>
            <div className="bg-surface-0 rounded-md border border-zinc-800">
              <JsonViewer data={selectedReplay.output} maxHeight="300px" />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
