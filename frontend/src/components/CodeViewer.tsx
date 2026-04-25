import React from "react";

interface Props {
  code: string;
}

export default function CodeViewer({ code }: Props) {
  if (!code) return null;

  return (
    <div className="code-viewer">
      <div className="code-viewer-header">Generated eval function</div>
      <pre className="code-viewer-body">
        <code>{code}</code>
      </pre>
    </div>
  );
}
