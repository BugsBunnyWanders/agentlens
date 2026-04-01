import { useState } from "react";
import { useTraces } from "../hooks/useTraces";
import { TraceListRow } from "./TraceListRow";

export function TraceList() {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("");
  const { data, loading, error, refetch } = useTraces(
    { limit: 100, status: statusFilter || undefined },
    true,
  );

  const filtered =
    data?.traces.filter((t) =>
      t.name.toLowerCase().includes(search.toLowerCase()),
    ) ?? [];

  return (
    <div className="max-w-7xl mx-auto px-4 py-6">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-lg font-semibold text-zinc-100">Traces</h1>
        <button
          onClick={() => refetch()}
          className="text-xs text-zinc-400 hover:text-zinc-200 px-2 py-1 rounded hover:bg-surface-2 transition-colors"
        >
          Refresh
        </button>
      </div>

      <div className="flex items-center gap-3 mb-4">
        <input
          type="text"
          placeholder="Search traces..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="bg-surface-1 border border-zinc-800 rounded-md px-3 py-1.5 text-sm text-zinc-200 placeholder-zinc-500 focus:outline-none focus:border-zinc-600 w-64"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="bg-surface-1 border border-zinc-800 rounded-md px-3 py-1.5 text-sm text-zinc-200 focus:outline-none focus:border-zinc-600"
        >
          <option value="">All statuses</option>
          <option value="running">Running</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
        </select>
        {data && (
          <span className="text-xs text-zinc-500">
            {data.total} total
          </span>
        )}
      </div>

      <div className="bg-surface-1 rounded-lg border border-zinc-800 overflow-hidden">
        <div className="grid grid-cols-[1fr_100px_90px_80px_80px_100px] gap-3 px-4 py-2 text-xs font-medium text-zinc-500 border-b border-zinc-800 uppercase tracking-wider">
          <span>Name</span>
          <span>Status</span>
          <span>Duration</span>
          <span>Tokens</span>
          <span>Cost</span>
          <span className="text-right">Time</span>
        </div>

        {loading && !data && (
          <div className="px-4 py-8 text-center text-zinc-500 text-sm">
            Loading...
          </div>
        )}

        {error && (
          <div className="px-4 py-8 text-center text-red-400 text-sm">
            Failed to load traces: {error.message}
          </div>
        )}

        {filtered.length === 0 && !loading && (
          <div className="px-4 py-8 text-center text-zinc-500 text-sm">
            No traces found. Run an agent with AgentLens tracing to see traces here.
          </div>
        )}

        {filtered.map((trace) => (
          <TraceListRow key={trace.id} trace={trace} />
        ))}
      </div>
    </div>
  );
}
