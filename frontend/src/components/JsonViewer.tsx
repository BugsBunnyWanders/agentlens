import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";

interface JsonViewerProps {
  data: unknown;
  maxHeight?: string;
}

export function JsonViewer({ data, maxHeight = "400px" }: JsonViewerProps) {
  const formatted =
    typeof data === "string" ? data : JSON.stringify(data, null, 2);

  if (!formatted || formatted === "null") {
    return <span className="text-zinc-500 text-xs italic">null</span>;
  }

  return (
    <div className="overflow-auto rounded-md" style={{ maxHeight }}>
      <SyntaxHighlighter
        language="json"
        style={vscDarkPlus}
        customStyle={{
          margin: 0,
          background: "transparent",
          fontSize: "0.8125rem",
          padding: "0.5rem",
        }}
        wrapLongLines
      >
        {formatted}
      </SyntaxHighlighter>
    </div>
  );
}
