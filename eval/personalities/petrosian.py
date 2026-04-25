"""Petrosian personality: king safety, pawn shield, prophylaxis."""
import chess


def evaluate(board: chess.Board) -> int:
    """Iron fortress — heavily rewards king safety and punishes any weaknesses."""
    if board.is_checkmate():
        return -900_000 if board.turn == chess.WHITE else 900_000

    score = 0

    MATERIAL = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
                chess.ROOK: 500, chess.QUEEN: 900}

    for pt, val in MATERIAL.items():
        score += val * len(board.pieces(pt, chess.WHITE))
        score -= val * len(board.pieces(pt, chess.BLACK))

    # King pawn shield
    white_king = board.king(chess.WHITE)
    black_king = board.king(chess.BLACK)

    if white_king is not None:
        king_file = chess.square_file(white_king)
        king_rank = chess.square_rank(white_king)
        for df in [-1, 0, 1]:
            f = king_file + df
            if 0 <= f <= 7:
                shield_sq = chess.square(f, min(king_rank + 1, 7))
                piece = board.piece_at(shield_sq)
                if piece and piece.piece_type == chess.PAWN and piece.color == chess.WHITE:
                    score += 20

    if black_king is not None:
        king_file = chess.square_file(black_king)
        king_rank = chess.square_rank(black_king)
        for df in [-1, 0, 1]:
            f = king_file + df
            if 0 <= f <= 7:
                shield_sq = chess.square(f, max(king_rank - 1, 0))
                piece = board.piece_at(shield_sq)
                if piece and piece.piece_type == chess.PAWN and piece.color == chess.BLACK:
                    score -= 20

    # Penalise open files near king
    if white_king is not None:
        for df in [-1, 0, 1]:
            f = chess.square_file(white_king) + df
            if 0 <= f <= 7:
                file_pawns = chess.SquareSet(board.pieces(chess.PAWN, chess.WHITE)) & chess.SquareSet(chess.BB_FILES[f])
                if not file_pawns:
                    score -= 15

    if black_king is not None:
        for df in [-1, 0, 1]:
            f = chess.square_file(black_king) + df
            if 0 <= f <= 7:
                file_pawns = chess.SquareSet(board.pieces(chess.PAWN, chess.BLACK)) & chess.SquareSet(chess.BB_FILES[f])
                if not file_pawns:
                    score += 15

    return score
