import React, { useEffect, useState } from "react";
import { Chessboard } from "react-chessboard";
import { Chess } from "chess.js";

interface Props {
  gameId: string | null;
  onMove: (moveUci: string) => void;
  fen: string;
  playerColor: "white" | "black";
  thinking: boolean;
}

export default function Board({ gameId, onMove, fen, playerColor, thinking }: Props) {
  const [displayFen, setDisplayFen] = useState(fen);
  const [selectedSquare, setSelectedSquare] = useState<string | null>(null);
  const [legalSquares, setLegalSquares] = useState<string[]>([]);

  useEffect(() => {
    setDisplayFen(fen);
    setSelectedSquare(null);
    setLegalSquares([]);
  }, [fen]);

  function getLegalTargets(square: string, fenStr: string): string[] {
    const chess = new Chess(fenStr);
    return chess.moves({ square: square as any, verbose: true }).map((m: any) => m.to);
  }

  function makeMove(from: string, to: string) {
    const chess = new Chess(displayFen);
    const move = chess.move({ from: from as any, to: to as any, promotion: "q" });
    if (!move) return false;
    setDisplayFen(chess.fen());
    onMove(move.from + move.to + (move.promotion ?? ""));
    setSelectedSquare(null);
    setLegalSquares([]);
    return true;
  }

  function onSquareClick(square: string) {
    if (!gameId) return;

    // If a piece is selected and this is a legal target → make the move
    if (selectedSquare && legalSquares.includes(square)) {
      makeMove(selectedSquare, square);
      return;
    }

    const chess = new Chess(displayFen);
    const piece = chess.get(square as any);
    const myColor = playerColor === "white" ? "w" : "b";

    // Click own piece → select it and show legal moves
    if (piece && piece.color === myColor) {
      setSelectedSquare(square);
      setLegalSquares(getLegalTargets(square, displayFen));
      return;
    }

    // Anything else → deselect
    setSelectedSquare(null);
    setLegalSquares([]);
  }

  function onDrop(sourceSquare: string, targetSquare: string): boolean {
    if (!gameId) return false;
    return makeMove(sourceSquare, targetSquare);
  }

  // Build square highlight styles
  const customSquareStyles: Record<string, React.CSSProperties> = {};

  if (selectedSquare) {
    customSquareStyles[selectedSquare] = { backgroundColor: "rgba(255, 214, 0, 0.55)" };
  }

  for (const sq of legalSquares) {
    const chess = new Chess(displayFen);
    const isCapture = !!chess.get(sq as any);
    customSquareStyles[sq] = isCapture
      ? { background: "radial-gradient(transparent 55%, rgba(255, 214, 0, 0.75) 55%)", borderRadius: "0%" }
      : { background: "radial-gradient(rgba(255, 214, 0, 0.65) 28%, transparent 28%)" };
  }

  return (
    <div className="board-wrapper">
      {thinking && (
        <div className="engine-thinking-bar">
          <span className="thinking-dot" />
          Engine is thinking…
        </div>
      )}
      <Chessboard
        position={displayFen}
        onPieceDrop={onDrop}
        onSquareClick={onSquareClick}
        boardOrientation={playerColor}
        animationDuration={350}
        customSquareStyles={customSquareStyles}
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
