"""Tal personality: maximizes piece activity and king attack zone bonuses."""
import chess


def evaluate(board: chess.Board) -> int:
    """Aggressive attacker — values open lines toward enemy king, ignores material safety."""
    if board.is_checkmate():
        return -900_000 if board.turn == chess.WHITE else 900_000

    score = 0

    MATERIAL = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330,
                chess.ROOK: 500, chess.QUEEN: 900}

    for pt, val in MATERIAL.items():
        score += val * len(board.pieces(pt, chess.WHITE))
        score -= val * len(board.pieces(pt, chess.BLACK))

    try:
        if board.turn == chess.WHITE:
            white_mobility = len(list(board.legal_moves))
            board.push(chess.Move.null())
            black_mobility = len(list(board.legal_moves))
            board.pop()
        else:
            black_mobility = len(list(board.legal_moves))
            board.push(chess.Move.null())
            white_mobility = len(list(board.legal_moves))
            board.pop()
        score += 5 * (white_mobility - black_mobility)
    except AssertionError:
        pass  # null move is illegal in check

    # King attack zone: bonus for pieces near enemy king
    black_king_sq = board.king(chess.BLACK)
    white_king_sq = board.king(chess.WHITE)

    if black_king_sq is not None:
        attack_zone = chess.SquareSet(chess.BB_KING_ATTACKS[black_king_sq])
        for sq in attack_zone:
            piece = board.piece_at(sq)
            if piece and piece.color == chess.WHITE:
                score += 30

    if white_king_sq is not None:
        attack_zone = chess.SquareSet(chess.BB_KING_ATTACKS[white_king_sq])
        for sq in attack_zone:
            piece = board.piece_at(sq)
            if piece and piece.color == chess.BLACK:
                score -= 30

    return score
