import { useState } from "react";
import { useNavigate } from "react-router-dom";
import CodeMirror from "@uiw/react-codemirror";
import { json } from "@codemirror/lang-json";
import { oneDark } from "@codemirror/theme-one-dark";
import { Modal } from "./Modal";
import { useReplay } from "../hooks/useReplay";
import type { Span } from "../types";
import { getDownstreamSpans } from "../lib/spans";

interface SpanEditorProps {
  open: boolean;
  onClose: () => void;
  span: Span;
  allSpans: Span[];
  traceId: string;
}

export function SpanEditor({ open, onClose, span, allSpans, traceId }: SpanEditorProps) {
  const [value, setValue] = useState(() =>
    JSON.stringify(span.output, null, 2) ?? "",
  );
  const { replay, loading, error } = useReplay();
  const navigate = useNavigate();
  const downstream = getDownstreamSpans(allSpans, span.id);

  const handleReplay = async () => {
    let parsedOutput: unknown;
    try {
      parsedOutput = JSON.parse(value);
    } catch {
      parsedOutput = value;
    }

    const result = await replay(traceId, [
      { span_id: span.id, new_output: parsedOutput },
    ]);

    if (result) {
      onClose();
      navigate(`/traces/${traceId}/replay/${result.replay_trace.id}`);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title={`Fork: ${span.name}`}>
      <div className="flex flex-col gap-4">
        <div>
          <div className="text-xs font-medium text-zinc-400 mb-2">
            Edit output for &ldquo;{span.name}&rdquo;
          </div>
          <CodeMirror
            value={value}
            height="300px"
            theme={oneDark}
            extensions={[json()]}
            onChange={(v) => setValue(v)}
            className="rounded-md border border-zinc-700 overflow-hidden"
          />
        </div>

        {downstream.length > 0 && (
          <div className="bg-surface-0 rounded-md border border-zinc-800 p-3">
            <div className="text-xs font-medium text-zinc-400 mb-1">
              Downstream spans ({downstream.length}) &mdash; will be marked as stale:
            </div>
            <div className="flex flex-wrap gap-1 mb-2">
              {downstream.map((s) => (
                <span
                  key={s.id}
                  className="text-xs bg-zinc-800 text-zinc-300 px-2 py-0.5 rounded"
                >
                  {s.name}
                </span>
              ))}
            </div>
            <div className="text-[11px] text-amber-400/70">
              Deterministic mode: downstream spans keep their original output but are marked as stale.
              Live re-execution coming in v0.2.
            </div>
          </div>
        )}

        {error && (
          <div className="text-xs text-red-400">Replay failed: {error.message}</div>
        )}

        <div className="flex justify-end gap-2">
          <button
            onClick={onClose}
            className="text-zinc-400 hover:text-zinc-200 hover:bg-surface-2 px-3 py-1.5 rounded-md text-sm transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleReplay}
            disabled={loading}
            className="bg-blue-600 hover:bg-blue-500 disabled:opacity-50 text-white px-4 py-1.5 rounded-md text-sm font-medium transition-colors"
          >
            {loading ? "Replaying..." : "Replay from here"}
          </button>
        </div>
      </div>
    </Modal>
  );
}
