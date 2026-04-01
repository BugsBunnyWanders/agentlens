import type { SpanKind } from "../types";

const icons: Record<SpanKind, string> = {
  llm: "\u{1F916}",
  tool: "\u{1F527}",
  retrieval: "\u{1F4DA}",
  chain: "\u26D3\uFE0F",
  agent: "\u{1F3AF}",
  custom: "\u2B50",
};

export function SpanKindIcon({ kind }: { kind: SpanKind }) {
  return <span title={kind}>{icons[kind] ?? "\u2B50"}</span>;
}
