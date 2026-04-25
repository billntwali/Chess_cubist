import React, { useState } from "react";
import { Chessboard } from "react-chessboard";
import { Chess } from "chess.js";

interface Props {
  evalPath: string;
  philosophy: string;
  gameId: string | null;
  onMove: (moveUci: string) => void;
  fen: string;
  playerColor: "white" | "black";
}

export default function Board({ evalPath, philosophy, gameId, onMove, fen, playerColor }: Props) {
  function onDrop(sourceSquare: string, targetSquare: string): boolean {
    if (!gameId) return false;
    const chess = new Chess(fen);
    const move = chess.move({ from: sourceSquare, to: targetSquare, promotion: "q" });
    if (!move) return false;
    onMove(move.from + move.to + (move.promotion ?? ""));
    return true;
  }

  return (
    <div className="board-wrapper">
      <Chessboard
        position={fen}
        onPieceDrop={onDrop}
        boardOrientation={playerColor}
        animationDuration={200}
      />
    </div>
  );
}
