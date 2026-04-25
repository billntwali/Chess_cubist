import React from "react";

interface Props {
  whiteProb: number; // 0.0 – 1.0
}

export default function WinProbBar({ whiteProb }: Props) {
  const whitePct = Math.round(whiteProb * 100);
  const blackPct = 100 - whitePct;

  return (
    <div className="win-prob-bar">
      <div className="win-prob-white" style={{ width: `${whitePct}%` }}>
        {whitePct > 10 && `${whitePct}%`}
      </div>
      <div className="win-prob-black" style={{ width: `${blackPct}%` }}>
        {blackPct > 10 && `${blackPct}%`}
      </div>
    </div>
  );
}
