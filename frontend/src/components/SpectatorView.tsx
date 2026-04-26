import React, { useEffect, useRef, useState } from "react";
import { Chessboard } from "react-chessboard";
import CommentaryFeed from "./CommentaryFeed";
import WinProbBar from "./WinProbBar";

interface Props {
  gameId: string;
}

export default function SpectatorView({ gameId }: Props) {
  const [fen, setFen] = useState("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
  const [whiteProb, setWhiteProb] = useState(0.5);
  const [commentary, setCommentary] = useState<string[]>([]);
  const [connected, setConnected] = useState(false);
  const [gameOver, setGameOver] = useState(false);
  const [resultText, setResultText] = useState("");
  const [showCommentary, setShowCommentary] = useState(true);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    const ws = new WebSocket(`ws://${window.location.host}/ws/spectate/${gameId}`);
    ws.onopen = () => setConnected(true);
    ws.onmessage = (e) => {
      const data = JSON.parse(e.data);
      if (data.fen) setFen(data.fen);
      if (data.white_prob !== undefined) setWhiteProb(data.white_prob);
      if (data.commentary) setCommentary((c) => [...c, data.commentary]);
      if (data.game_over) {
        const status = data.result_text || "Game over";
        setGameOver(true);
        setResultText(status);
        if (!data.commentary) {
          setCommentary((c) => [...c, status]);
        }
      }
    };
    ws.onclose = () => setConnected(false);
    wsRef.current = ws;
    return () => ws.close();
  }, [gameId]);

  return (
    <div className="app">
      <header>
        <div className="header-logo">♟ Chess Forge</div>
        <div className="philosophy-badge">
          {gameOver ? resultText : connected ? "Spectating live" : "Connecting…"}
        </div>
      </header>

      <div className="center-panel" style={{ margin: "0 auto" }}>
        <WinProbBar whiteProb={whiteProb} />
        {gameOver && <div className="game-over-banner">{resultText}</div>}
        <div className="board-wrapper">
          <Chessboard
            position={fen}
            arePiecesDraggable={false}
            animationDuration={350}
            customBoardStyle={{
              borderRadius: "8px",
              boxShadow: "0 8px 40px rgba(0,0,0,0.6)",
            }}
            customDarkSquareStyle={{ backgroundColor: "#3d2f6e" }}
            customLightSquareStyle={{ backgroundColor: "#c8b9e8" }}
          />
        </div>
        {!connected && (
          <p style={{ textAlign: "center", color: "#aaa", marginTop: "1rem" }}>
            Waiting for game to start…
          </p>
        )}
      </div>

      <div className="right-panel">
        {showCommentary && <CommentaryFeed lines={commentary} onClose={() => setShowCommentary(false)} />}
      </div>
    </div>
  );
}
