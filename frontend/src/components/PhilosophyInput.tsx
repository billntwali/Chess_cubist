import React, { useState } from "react";

interface HistoryEntry {
  description: string;
  interpreted: string;
  evalPath: string;
  code: string;
}

interface Props {
  onEvalReady: (evalPath: string, code: string, philosophy: string) => void;
}

export default function PhilosophyInput({ onEvalReady }: Props) {
  const [description, setDescription] = useState("");
  const [interpreted, setInterpreted] = useState("");
  const [code, setCode] = useState("");
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [status, setStatus] = useState<"idle" | "interpreting" | "generating" | "validating" | "ready" | "error">("idle");
  const [error, setError] = useState("");

  async function handleGenerate() {
    setStatus("interpreting");
    setError("");
    setInterpreted("");

    try {
      const interpRes = await fetch("/api/interpret", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ description }),
      });
      if (!interpRes.ok) throw new Error("Backend unreachable — is it running?");
      const { interpreted: interp } = await interpRes.json();
      setInterpreted(interp);
      setStatus("generating");

      const genRes = await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ interpreted: interp }),
      });
      if (!genRes.ok) throw new Error("Generation request failed");
      const data = await genRes.json();

      if (!data.ok) {
        setStatus("error");
        setError(data.error);
        return;
      }

      setCode(data.code);
      setStatus("ready");
      setHistory((h) => [{ description, interpreted: interp, evalPath: data.eval_path, code: data.code }, ...h]);
      onEvalReady(data.eval_path, data.code, description);
    } catch (e: any) {
      setStatus("error");
      setError(e.message ?? "Something went wrong — check the backend is running on port 8000.");
    }
  }

  return (
    <div className="philosophy-input">
      <textarea
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        placeholder="Describe a chess philosophy... e.g. 'A coward that retreats everything and never attacks'"
        rows={3}
      />
      <button onClick={handleGenerate} disabled={!description || status === "interpreting" || status === "generating"}>
        {status === "interpreting" ? "Interpreting..." : status === "generating" ? "Generating..." : "Generate"}
      </button>

      {interpreted && (
        <div className="interpreted">
          <strong>Playing style:</strong> {interpreted}
        </div>
      )}

      {status === "error" && <div className="error">{error}</div>}

      {history.length > 0 && (
        <div className="history">
          <strong>Previous versions</strong>
          {history.map((entry, i) => (
            <div key={i} className="history-entry" onClick={() => onEvalReady(entry.evalPath, entry.code, entry.description)}>
              v{history.length - i}: {entry.description.slice(0, 50)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
