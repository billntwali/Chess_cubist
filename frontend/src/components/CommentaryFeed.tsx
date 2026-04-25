import React, { useEffect, useRef } from "react";

interface Props {
  lines: string[];
}

export default function CommentaryFeed({ lines }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  if (lines.length === 0) return null;

  return (
    <div style={{ display: "flex", flexDirection: "column", flex: 1, minHeight: 0 }}>
      <div className="commentary-label">Commentary</div>
      <div className="commentary-feed">
        {lines.map((line, i) => (
          <p key={i} className="commentary-line">{line}</p>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
