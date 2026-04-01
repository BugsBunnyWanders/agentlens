import { useState } from "react";
import { useNavigate } from "react-router-dom";
import CodeMirror from "@uiw/react-codemirror";
import { json } from "@codemirror/lang-json";
import { oneDark } from "@codemirror/theme-one-dark";
import { Modal } from "./Modal";
import { useReplay } from "../hooks/useReplay";
import type { Span, ReplayMode } from "../types";
import { getDownstreamSpans } from "../lib/spans";

interface SpanEditorProps {
  open: boolean;
  onClose: () => void;
  span: Span;
  allSpans: Span[];
  traceId: string;
}

const MODE_INFO: Record<ReplayMode, { label: string; description: string; color: string }> = {
  deterministic: {
    label: "Deterministic",
    description: "Downstream spans keep original output (marked stale). No API calls.",
    color: "text-zinc-300",
  },
  live: {
    label: "Live",
    description: "All downstream spans re-execute with real API calls. May incur costs.",
    color: "text-green-400",
  },
  hybrid: {
    label: "Hybrid",
    description: "LLM calls re-execute live, tool calls use recorded responses.",
    color: "text-blue-400",
  },
};

export function SpanEditor({ open, onClose, span, allSpans, traceId }: SpanEditorProps) {
  const [value, setValue] = useState(() =>
    JSON.stringify(span.output, null, 2) ?? "",
  );
  const [mode, setMode] = useState<ReplayMode>("deterministic");
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

    const result = await replay(
      traceId,
      [{ span_id: span.id, new_output: parsedOutput }],
      mode,
    );

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
            height="250px"
            theme={oneDark}
            extensions={[json()]}
            onChange={(v) => setValue(v)}
            className="rounded-md border border-zinc-700 overflow-hidden"
          />
        </div>

        <div>
          <div className="text-xs font-medium text-zinc-400 mb-2">Replay Mode</div>
          <div className="flex gap-2">
            {(Object.keys(MODE_INFO) as ReplayMode[]).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                className={`px-3 py-1.5 rounded-md text-xs font-medium border transition-colors ${
                  mode === m
                    ? "bg-surface-3 border-zinc-600 text-zinc-100"
                    : "bg-surface-0 border-zinc-800 text-zinc-500 hover:text-zinc-300 hover:border-zinc-700"
                }`}
              >
                {MODE_INFO[m].label}
              </button>
            ))}
          </div>
          <div className={`text-xs mt-1.5 ${MODE_INFO[mode].color}`}>
            {MODE_INFO[mode].description}
          </div>
        </div>

        {downstream.length > 0 && (
          <div className="bg-surface-0 rounded-md border border-zinc-800 p-3">
            <div className="text-xs font-medium text-zinc-400 mb-1">
              Downstream spans ({downstream.length}):
            </div>
            <div className="flex flex-wrap gap-1">
              {downstream.map((s) => (
                <span
                  key={s.id}
                  className="text-xs bg-zinc-800 text-zinc-300 px-2 py-0.5 rounded"
                >
                  {s.name}
                </span>
              ))}
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
            {loading ? (mode === "deterministic" ? "Replaying..." : "Re-executing...") : "Replay from here"}
          </button>
        </div>
      </div>
    </Modal>
  );
}
