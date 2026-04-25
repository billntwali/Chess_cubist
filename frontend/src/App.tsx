import React, { useEffect, useRef, useState } from "react";
import Board from "./components/Board";
import CodeViewer from "./components/CodeViewer";
import CommentaryFeed from "./components/CommentaryFeed";
import EngineInfo from "./components/EngineInfo";
import PhilosophyInput from "./components/PhilosophyInput";
import SpectatorRoom from "./components/SpectatorRoom";
import TournamentResults from "./components/TournamentResults";
import WinProbBar from "./components/WinProbBar";

export default function App() {
  const [evalPath, setEvalPath] = useState("");
  const [code, setCode] = useState("");
  const [philosophy, setPhilosophy] = useState("");
  const [gameId, setGameId] = useState<string | null>(null);
  const [fen, setFen] = useState("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
  const [evalCp, setEvalCp] = useState(0);
  const [whiteProb, setWhiteProb] = useState(0.5);
  const [pv, setPv] = useState("");
  const [depth, setDepth] = useState(0);
  const [commentary, setCommentary] = useState<string[]>([]);
  const [viewerCount, setViewerCount] = useState(0);
  const [tournamentStandings, setTournamentStandings] = useState([]);
  const [tournamentRunning, setTournamentRunning] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  function handleEvalReady(path: string, evalCode: string, desc: string) {
    setEvalPath(path);
    setCode(evalCode);
    setPhilosophy(desc);
    setGameId(null);
  }

  async function startGame() {
    try {
      const res = await fetch("/api/game/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ eval_path: evalPath, philosophy }),
      });
      if (!res.ok) {
        const err = await res.text();
        alert(`Failed to start game: ${err}`);
        return;
      }
      const { game_id } = await res.json();
      setGameId(game_id);

      const ws = new WebSocket(`ws://${window.location.host}/ws/game/${game_id}`);
      ws.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.error) { alert(`Engine error: ${data.error}`); return; }
        if (data.fen) setFen(data.fen);
        if (data.eval_cp !== undefined) setEvalCp(data.eval_cp);
        if (data.white_prob !== undefined) setWhiteProb(data.white_prob);
        if (data.pv) setPv(data.pv);
        if (data.depth) setDepth(data.depth);
        if (data.commentary) setCommentary((c) => [...c, data.commentary]);
      };
      ws.onerror = () => alert("WebSocket connection failed — is the backend running?");
      wsRef.current = ws;
    } catch (e) {
      alert(`Could not reach backend — is it running on port 8000?`);
    }
  }

  function handleMove(moveUci: string) {
    wsRef.current?.send(JSON.stringify({ move: moveUci }));
  }

  async function runTournament() {
    setTournamentRunning(true);
    setTournamentStandings([]);
    try {
      const res = await fetch("/api/tournament", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_eval_path: evalPath, user_name: philosophy.slice(0, 20) }),
      });
      const data = await res.json();
      const standings = Object.entries(data.standings).map(([name, record]: [string, any]) => ({
        name,
        ...record,
      }));
      setTournamentStandings(standings);
    } finally {
      setTournamentRunning(false);
    }
  }

  return (
    <div className="app">
      <header><h1>Chess Forge</h1></header>

      <div className="left-panel">
        <PhilosophyInput onEvalReady={handleEvalReady} />
        {evalPath && !gameId && (
          <button onClick={startGame}>Play</button>
        )}
        {gameId && (
          <button onClick={runTournament} disabled={tournamentRunning}>
            {tournamentRunning ? "Running tournament… (1–2 min)" : "Run Tournament"}
          </button>
        )}
        <CodeViewer code={code} />
      </div>

      <div className="center-panel">
        <WinProbBar whiteProb={whiteProb} />
        <Board
          evalPath={evalPath}
          philosophy={philosophy}
          gameId={gameId}
          onMove={handleMove}
          fen={fen}
          playerColor="white"
        />
        <EngineInfo depth={depth} evalCp={evalCp} pv={pv} />
        <SpectatorRoom gameId={gameId} viewerCount={viewerCount} />
      </div>

      <div className="right-panel">
        <CommentaryFeed lines={commentary} />
        <TournamentResults standings={tournamentStandings} />
      </div>
    </div>
  );
}
