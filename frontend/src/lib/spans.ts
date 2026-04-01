import type { Span, SpanNode } from "../types";

export function buildSpanTree(spans: Span[]): SpanNode[] {
  const sorted = [...spans].sort((a, b) => a.sequence - b.sequence);
  const nodeMap = new Map<string, SpanNode>();
  const roots: SpanNode[] = [];

  for (const span of sorted) {
    const node: SpanNode = { ...span, children: [], depth: 0 };
    nodeMap.set(span.id, node);
  }

  for (const span of sorted) {
    const node = nodeMap.get(span.id)!;
    if (span.parent_span_id && nodeMap.has(span.parent_span_id)) {
      const parent = nodeMap.get(span.parent_span_id)!;
      node.depth = parent.depth + 1;
      parent.children.push(node);
    } else {
      roots.push(node);
    }
  }

  return roots;
}

export function flattenSpanTree(roots: SpanNode[]): SpanNode[] {
  const result: SpanNode[] = [];
  function walk(nodes: SpanNode[]) {
    for (const node of nodes) {
      result.push(node);
      walk(node.children);
    }
  }
  walk(roots);
  return result;
}

export function getDownstreamSpans(spans: Span[], spanId: string): Span[] {
  const target = spans.find((s) => s.id === spanId);
  if (!target) return [];
  return spans.filter((s) => s.sequence > target.sequence);
}

export function getSpanDurationMs(span: Span): number | null {
  if (!span.started_at || !span.ended_at) return null;
  return new Date(span.ended_at).getTime() - new Date(span.started_at).getTime();
}
