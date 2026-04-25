import React, { useRef, useState } from "react";
import Board from "./components/Board";
import CommentaryFeed from "./components/CommentaryFeed";
import EngineInfo from "./components/EngineInfo";
import PhilosophyInput from "./components/PhilosophyInput";
import SpectatorRoom from "./components/SpectatorRoom";
import TournamentResults from "./components/TournamentResults";
import WinProbBar from "./components/WinProbBar";

export default function App() {
  const [evalPath, setEvalPath] = useState("");
  const [philosophy, setPhilosophy] = useState("");
  const [gameId, setGameId] = useState<string | null>(null);
  const [fen, setFen] = useState("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
  const [evalCp, setEvalCp] = useState(0);
  const [whiteProb, setWhiteProb] = useState(0.5);
  const [pv, setPv] = useState("");
  const [depth, setDepth] = useState(0);
  const [commentary, setCommentary] = useState<string[]>([]);
  const [viewerCount, setViewerCount] = useState(0);
  const [tournamentStandings, setTournamentStandings] = useState<any[]>([]);
  const [tournamentRunning, setTournamentRunning] = useState(false);
  const [thinking, setThinking] = useState(false);
  const [playerTurn, setPlayerTurn] = useState(false);
  const [showEngineInfo, setShowEngineInfo] = useState(true);
  const [showCommentary, setShowCommentary] = useState(true);
  const wsRef = useRef<WebSocket | null>(null);

  function handleEvalReady(path: string, _code: string, desc: string) {
    setEvalPath(path);
    setPhilosophy(desc);
    setGameId(null);
    setFen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
    setCommentary([]);
    setPlayerTurn(false);
    setWhiteProb(0.5);
    setEvalCp(0);
    setPv("");
    setDepth(0);
  }

  async function startGame() {
    try {
      const res = await fetch("/api/game/start", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ eval_path: evalPath, philosophy }),
      });
      if (!res.ok) { alert(`Failed to start game: ${await res.text()}`); return; }
      const { game_id } = await res.json();
      setGameId(game_id);

      setPlayerTurn(true);
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
        setThinking(false);
        setPlayerTurn(true);
      };
      ws.onerror = () => alert("WebSocket connection failed — is the backend running?");
      wsRef.current = ws;
    } catch {
      alert("Could not reach backend — is it running on port 8000?");
    }
  }

  function handleMove(moveUci: string) {
    setThinking(true);
    setPlayerTurn(false);
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
      if (!res.ok) {
        const text = await res.text();
        alert(`Tournament failed: ${text}`);
        return;
      }
      const data = await res.json();
      setTournamentStandings(
        Object.entries(data.standings).map(([name, record]: [string, any]) => ({ name, ...record }))
      );
    } catch (err) {
      alert(`Tournament error: ${err}`);
    } finally {
      setTournamentRunning(false);
    }
  }

  return (
    <div className="app">
      <header>
        <div className="header-logo">♟ Chess Forge</div>
        {thinking && <div className="thinking-badge">Engine thinking…</div>}
        {philosophy && <div className="philosophy-badge">"{philosophy.slice(0, 40)}{philosophy.length > 40 ? '…' : ''}"</div>}
      </header>

      <div className="left-panel">
        <PhilosophyInput onEvalReady={handleEvalReady} />
        {evalPath && !gameId && (
          <button className="btn-primary" onClick={startGame}>▶ Play</button>
        )}
        {gameId && (
          <button className="btn-secondary" onClick={runTournament} disabled={tournamentRunning}>
            {tournamentRunning ? "⏳ Running tournament…" : "⚔ Run Tournament"}
          </button>
        )}
        <TournamentResults standings={tournamentStandings} />
      </div>

      <div className="center-panel">
        <WinProbBar whiteProb={whiteProb} />
        <Board
          gameId={gameId}
          onMove={handleMove}
          fen={fen}
          playerColor="white"
          thinking={thinking}
          playerTurn={playerTurn}
        />
        {showEngineInfo && <EngineInfo depth={depth} evalCp={evalCp} pv={pv} onClose={() => setShowEngineInfo(false)} />}
        <SpectatorRoom gameId={gameId} viewerCount={viewerCount} />
      </div>

      <div className="right-panel">
        {showCommentary && <CommentaryFeed lines={commentary} onClose={() => setShowCommentary(false)} />}
      </div>
    </div>
  );
}
