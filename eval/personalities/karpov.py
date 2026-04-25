"""Karpov personality: outposts, pawn structure, weak squares, long-term pressure."""
import chess


def evaluate(board: chess.Board) -> int:
    """Positional squeeze — rewards outpost knights, penalises doubled/isolated pawns."""
    if board.is_checkmate():
        return -900_000 if board.turn == chess.WHITE else 900_000

    score = 0

    MATERIAL = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
                chess.ROOK: 500, chess.QUEEN: 900}

    for pt, val in MATERIAL.items():
        score += val * len(board.pieces(pt, chess.WHITE))
        score -= val * len(board.pieces(pt, chess.BLACK))

    # Doubled pawn penalty
    for file in range(8):
        file_mask = chess.BB_FILES[file]
        white_pawns = len(chess.SquareSet(board.pieces(chess.PAWN, chess.WHITE)) & chess.SquareSet(file_mask))
        black_pawns = len(chess.SquareSet(board.pieces(chess.PAWN, chess.BLACK)) & chess.SquareSet(file_mask))
        if white_pawns > 1:
            score -= 20 * (white_pawns - 1)
        if black_pawns > 1:
            score += 20 * (black_pawns - 1)

    # Outpost bonus: knight on rank 4-6 not attackable by enemy pawns
    for sq in board.pieces(chess.KNIGHT, chess.WHITE):
        rank = chess.square_rank(sq)
        if rank >= 3:  # rank 4-8
            attackers = board.attackers(chess.BLACK, sq)
            if not any(board.piece_at(s) and board.piece_at(s).piece_type == chess.PAWN for s in attackers):
                score += 25

    for sq in board.pieces(chess.KNIGHT, chess.BLACK):
        rank = chess.square_rank(sq)
        if rank <= 4:  # rank 1-5 from black's view
            attackers = board.attackers(chess.WHITE, sq)
            if not any(board.piece_at(s) and board.piece_at(s).piece_type == chess.PAWN for s in attackers):
                score -= 25

    # Bishop pair bonus
    if len(board.pieces(chess.BISHOP, chess.WHITE)) >= 2:
        score += 50
    if len(board.pieces(chess.BISHOP, chess.BLACK)) >= 2:
        score -= 50

    return score
