import React from "react";

interface Props {
  depth: number;
  evalCp: number;
  pv: string;
  onClose: () => void;
}

export default function EngineInfo({ depth, evalCp, pv, onClose }: Props) {
  const evalLabel = evalCp > 0 ? `+${(evalCp / 100).toFixed(2)}` : (evalCp / 100).toFixed(2);

  return (
    <div className="engine-info">
      <span className="engine-depth">depth {depth}</span>
      <span className="engine-eval">score {evalLabel}</span>
      <span className="engine-pv">pv: {pv}</span>
      <button className="panel-close-btn" onClick={onClose} title="Hide eval bar">×</button>
    </div>
  );
}
