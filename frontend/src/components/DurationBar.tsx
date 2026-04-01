interface DurationBarProps {
  durationMs: number | null;
  totalMs: number | null;
}

export function DurationBar({ durationMs, totalMs }: DurationBarProps) {
  if (durationMs == null || totalMs == null || totalMs === 0) return null;
  const pct = Math.min(100, (durationMs / totalMs) * 100);
  return (
    <div className="w-16 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
      <div
        className="h-full bg-blue-500/60 rounded-full"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
