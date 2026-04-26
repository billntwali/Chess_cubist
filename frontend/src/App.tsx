import React, { useEffect, useRef, useState } from "react";
import Board from "./components/Board";
import CommentaryFeed from "./components/CommentaryFeed";
import EngineInfo from "./components/EngineInfo";
import PhilosophyInput from "./components/PhilosophyInput";
import SpectatorRoom from "./components/SpectatorRoom";
import SpectatorView from "./components/SpectatorView";
import TournamentResults from "./components/TournamentResults";
import WinProbBar from "./components/WinProbBar";

export default function App() {
  const spectateMatch = window.location.pathname.match(/^\/spectate\/([a-f0-9]+)$/);
  if (spectateMatch) {
    return <SpectatorView gameId={spectateMatch[1]} />;
  }
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
  const [gameOver, setGameOver] = useState(false);
  const [resultText, setResultText] = useState("");
  const [showEngineInfo, setShowEngineInfo] = useState(true);
  const [showCommentary, setShowCommentary] = useState(true);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    return () => wsRef.current?.close();
  }, []);

  function handleEvalReady(path: string, _code: string, desc: string) {
    wsRef.current?.close();
    wsRef.current = null;
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
    setViewerCount(0);
    setGameOver(false);
    setResultText("");
    setThinking(false);
    setShowEngineInfo(true);
    setShowCommentary(true);
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
      setFen("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
      setCommentary([]);
      setWhiteProb(0.5);
      setEvalCp(0);
      setPv("");
      setDepth(0);
      setViewerCount(0);
      setGameOver(false);
      setResultText("");

      setPlayerTurn(true);
      wsRef.current?.close();
      const ws = new WebSocket(`ws://${window.location.host}/ws/game/${game_id}`);
      ws.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.viewer_count !== undefined) { setViewerCount(data.viewer_count); return; }
        if (data.error) { alert(`Engine error: ${data.error}`); setThinking(false); return; }
        if (data.fen) setFen(data.fen);
        if (data.eval_cp !== undefined) setEvalCp(data.eval_cp);
        if (data.white_prob !== undefined) setWhiteProb(data.white_prob);
        if (data.pv !== undefined) setPv(data.pv);
        if (data.depth !== undefined) setDepth(data.depth);
        if (data.commentary) setCommentary((c) => [...c, data.commentary]);
        if (data.game_over) {
          const status = data.result_text || "Game over";
          setGameOver(true);
          setResultText(status);
          if (!data.commentary) {
            setCommentary((c) => [...c, status]);
          }
          setThinking(false);
          setPlayerTurn(false);
          return;
        }
        setThinking(false);
        setPlayerTurn(true);
      };
      ws.onclose = () => {
        setThinking(false);
      };
      ws.onerror = () => alert("WebSocket connection failed — is the backend running?");
      wsRef.current = ws;
    } catch {
      alert("Could not reach backend — is it running on port 8000?");
    }
  }

  function handleMove(moveUci: string) {
    if (!wsRef.current || gameOver) return;
    setThinking(true);
    setPlayerTurn(false);
    wsRef.current?.send(JSON.stringify({ move: moveUci }));
  }

  function forfeitGame() {
    if (!wsRef.current || !gameId || gameOver) return;
    wsRef.current.send(JSON.stringify({ action: "forfeit" }));
    setThinking(false);
    setPlayerTurn(false);
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
          <div className="game-controls">
            <button className="btn-secondary" onClick={runTournament} disabled={tournamentRunning}>
              {tournamentRunning ? "⏳ Running tournament…" : "⚔ Run Tournament"}
            </button>
            <button className="btn-danger" onClick={forfeitGame} disabled={gameOver}>
              🚩 Forfeit
            </button>
          </div>
        )}
        <TournamentResults standings={tournamentStandings} />
      </div>

      <div className="center-panel">
        <WinProbBar whiteProb={whiteProb} />
        {gameOver && <div className="game-over-banner">{resultText}</div>}
        <Board
          gameId={gameId}
          onMove={handleMove}
          fen={fen}
          playerColor="white"
          thinking={thinking}
          playerTurn={playerTurn}
          gameOver={gameOver}
          resultText={resultText}
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
