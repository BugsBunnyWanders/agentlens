import { useEffect } from "react";
import type { SpanNode } from "../types";

interface KeyboardNavOptions {
  spans: SpanNode[];
  selectedSpanId: string | null;
  setSelectedSpanId: (id: string) => void;
  openEditor: (spanId: string) => void;
  isEditorOpen: boolean;
}

export function useKeyboardNav({
  spans,
  selectedSpanId,
  setSelectedSpanId,
  openEditor,
  isEditorOpen,
}: KeyboardNavOptions) {
  useEffect(() => {
    if (isEditorOpen) return;

    function handleKeyDown(e: KeyboardEvent) {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      const currentIndex = spans.findIndex((s) => s.id === selectedSpanId);

      switch (e.key) {
        case "ArrowDown":
        case "j":
          e.preventDefault();
          if (currentIndex < spans.length - 1) {
            setSelectedSpanId(spans[currentIndex + 1].id);
          } else if (currentIndex === -1 && spans.length > 0) {
            setSelectedSpanId(spans[0].id);
          }
          break;
        case "ArrowUp":
        case "k":
          e.preventDefault();
          if (currentIndex > 0) {
            setSelectedSpanId(spans[currentIndex - 1].id);
          }
          break;
        case "e":
          if (selectedSpanId) {
            e.preventDefault();
            openEditor(selectedSpanId);
          }
          break;
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [spans, selectedSpanId, isEditorOpen, setSelectedSpanId, openEditor]);
}
