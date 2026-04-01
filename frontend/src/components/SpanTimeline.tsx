import { useEffect, useRef } from "react";
import type { SpanNode } from "../types";
import { SpanTimelineItem } from "./SpanTimelineItem";

interface SpanTimelineProps {
  spans: SpanNode[];
  selectedSpanId: string | null;
  onSelectSpan: (id: string) => void;
  totalDurationMs: number | null;
}

export function SpanTimeline({
  spans,
  selectedSpanId,
  onSelectSpan,
  totalDurationMs,
}: SpanTimelineProps) {
  const selectedRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    selectedRef.current?.scrollIntoView({ block: "nearest" });
  }, [selectedSpanId]);

  return (
    <div className="flex flex-col divide-y divide-zinc-800/50">
      {spans.map((span) => (
        <div
          key={span.id}
          ref={span.id === selectedSpanId ? selectedRef : undefined}
        >
          <SpanTimelineItem
            span={span}
            isSelected={span.id === selectedSpanId}
            totalDurationMs={totalDurationMs}
            onClick={() => onSelectSpan(span.id)}
          />
        </div>
      ))}
    </div>
  );
}
