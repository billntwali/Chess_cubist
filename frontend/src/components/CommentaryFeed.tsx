import React, { useEffect, useRef } from "react";

interface Props {
  lines: string[];
}

export default function CommentaryFeed({ lines }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  return (
    <div className="commentary-feed">
      {lines.map((line, i) => (
        <p key={i} className="commentary-line">{line}</p>
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
