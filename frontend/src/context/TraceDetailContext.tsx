import { createContext, useContext, useState, useCallback, type ReactNode } from "react";

interface TraceDetailState {
  selectedSpanId: string | null;
  setSelectedSpanId: (id: string | null) => void;
  isEditorOpen: boolean;
  editorSpanId: string | null;
  openEditor: (spanId: string) => void;
  closeEditor: () => void;
}

const TraceDetailContext = createContext<TraceDetailState | null>(null);

export function TraceDetailProvider({ children }: { children: ReactNode }) {
  const [selectedSpanId, setSelectedSpanId] = useState<string | null>(null);
  const [editorSpanId, setEditorSpanId] = useState<string | null>(null);
  const [isEditorOpen, setIsEditorOpen] = useState(false);

  const openEditor = useCallback((spanId: string) => {
    setEditorSpanId(spanId);
    setIsEditorOpen(true);
  }, []);

  const closeEditor = useCallback(() => {
    setIsEditorOpen(false);
    setEditorSpanId(null);
  }, []);

  return (
    <TraceDetailContext.Provider
      value={{
        selectedSpanId,
        setSelectedSpanId,
        isEditorOpen,
        editorSpanId,
        openEditor,
        closeEditor,
      }}
    >
      {children}
    </TraceDetailContext.Provider>
  );
}

export function useTraceDetail() {
  const ctx = useContext(TraceDetailContext);
  if (!ctx) throw new Error("useTraceDetail must be used within TraceDetailProvider");
  return ctx;
}
