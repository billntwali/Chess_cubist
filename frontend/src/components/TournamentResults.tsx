import React from "react";

interface Standing {
  name: string;
  W: number;
  D: number;
  L: number;
}

interface Props {
  standings: Standing[];
}

export default function TournamentResults({ standings }: Props) {
  if (!standings.length) return null;

  const sorted = [...standings].sort((a, b) => (b.W * 2 + b.D) - (a.W * 2 + a.D));
  const maxPoints = Math.max(...sorted.map((s) => s.W * 2 + s.D)) || 1;

  return (
    <div className="tournament-results">
      <h3>Tournament Results</h3>
      {sorted.map((s) => {
        const points = s.W * 2 + s.D;
        const pct = (points / maxPoints) * 100;
        return (
          <div key={s.name} className="result-row">
            <span className="result-name">{s.name}</span>
            <div className="result-bar" style={{ width: `${pct}%` }} />
            <span className="result-record">{s.W}W / {s.D}D / {s.L}L</span>
          </div>
        );
      })}
    </div>
  );
}
