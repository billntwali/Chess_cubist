import React from "react";

interface Props {
  depth: number;
  evalCp: number;
  pv: string;
}

export default function EngineInfo({ depth, evalCp, pv }: Props) {
  const evalLabel = evalCp > 0 ? `+${(evalCp / 100).toFixed(2)}` : (evalCp / 100).toFixed(2);

  return (
    <div className="engine-info">
      <span className="engine-depth">depth {depth}</span>
      <span className="engine-eval">score {evalLabel}</span>
      <span className="engine-pv">pv: {pv}</span>
    </div>
  );
}
