import React, { useEffect, useState } from "react";
import { Chessboard } from "react-chessboard";
import { Chess } from "chess.js";

interface Props {
  gameId: string | null;
  onMove: (moveUci: string) => void;
  fen: string;
  playerColor: "white" | "black";
}

export default function Board({ gameId, onMove, fen, playerColor }: Props) {
  // displayFen updates immediately on player move (optimistic),
  // then syncs to fen when the engine responds.
  const [displayFen, setDisplayFen] = useState(fen);

  useEffect(() => {
    setDisplayFen(fen);
  }, [fen]);

  function onDrop(sourceSquare: string, targetSquare: string): boolean {
    if (!gameId) return false;
    const chess = new Chess(displayFen);
    const move = chess.move({ from: sourceSquare, to: targetSquare, promotion: "q" });
    if (!move) return false;

    // Optimistically show the player's move immediately
    setDisplayFen(chess.fen());
    onMove(move.from + move.to + (move.promotion ?? ""));
    return true;
  }

  return (
    <div className="board-wrapper">
      <Chessboard
        position={displayFen}
        onPieceDrop={onDrop}
        boardOrientation={playerColor}
        animationDuration={350}
        customBoardStyle={{
          borderRadius: "8px",
          boxShadow: "0 8px 40px rgba(0,0,0,0.6)",
        }}
        customDarkSquareStyle={{ backgroundColor: "#3d2f6e" }}
        customLightSquareStyle={{ backgroundColor: "#c8b9e8" }}
      />
    </div>
  );
}
