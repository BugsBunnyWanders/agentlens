import type { TraceStatus, SpanStatus } from "../types";

const statusStyles: Record<string, string> = {
  running: "text-yellow-400 bg-yellow-400/10",
  completed: "text-emerald-400 bg-emerald-400/10",
  failed: "text-red-400 bg-red-400/10",
  cancelled: "text-zinc-400 bg-zinc-400/10",
};

export function StatusBadge({ status }: { status: TraceStatus | SpanStatus }) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${statusStyles[status] ?? statusStyles.cancelled}`}
    >
      {status}
    </span>
  );
}
