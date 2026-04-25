"""Baseline material + piece-square table evaluation."""
import chess

MATERIAL = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 0,
}

# Piece-square tables (white's perspective, a1=index 0)
PAWN_PST = [
     0,  0,  0,  0,  0,  0,  0,  0,
    50, 50, 50, 50, 50, 50, 50, 50,
    10, 10, 20, 30, 30, 20, 10, 10,
     5,  5, 10, 25, 25, 10,  5,  5,
     0,  0,  0, 20, 20,  0,  0,  0,
     5, -5,-10,  0,  0,-10, -5,  5,
     5, 10, 10,-20,-20, 10, 10,  5,
     0,  0,  0,  0,  0,  0,  0,  0,
]

KNIGHT_PST = [
    -50,-40,-30,-30,-30,-30,-40,-50,
    -40,-20,  0,  0,  0,  0,-20,-40,
    -30,  0, 10, 15, 15, 10,  0,-30,
    -30,  5, 15, 20, 20, 15,  5,-30,
    -30,  0, 15, 20, 20, 15,  0,-30,
    -30,  5, 10, 15, 15, 10,  5,-30,
    -40,-20,  0,  5,  5,  0,-20,-40,
    -50,-40,-30,-30,-30,-30,-40,-50,
]


def _pst_score(board: chess.Board, piece_type: int, pst: list[int], color: chess.Color) -> int:
    score = 0
    for sq in board.pieces(piece_type, color):
        idx = sq if color == chess.WHITE else chess.square_mirror(sq)
        score += pst[idx]
    return score


def evaluate(board: chess.Board) -> int:
    """Return centipawn score from White's perspective."""
    if board.is_checkmate():
        return -900_000 if board.turn == chess.WHITE else 900_000

    score = 0
    for piece_type, value in MATERIAL.items():
        score += value * len(board.pieces(piece_type, chess.WHITE))
        score -= value * len(board.pieces(piece_type, chess.BLACK))

    score += _pst_score(board, chess.PAWN, PAWN_PST, chess.WHITE)
    score -= _pst_score(board, chess.PAWN, PAWN_PST, chess.BLACK)
    score += _pst_score(board, chess.KNIGHT, KNIGHT_PST, chess.WHITE)
    score -= _pst_score(board, chess.KNIGHT, KNIGHT_PST, chess.BLACK)

    return score
