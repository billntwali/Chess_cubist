"""Eval sanity tests for classic.py and personality evals."""
import chess
import pytest

from eval.classic import evaluate as classic_eval
from eval.personalities.tal import evaluate as tal_eval
from eval.personalities.karpov import evaluate as karpov_eval
from eval.personalities.petrosian import evaluate as petrosian_eval

START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
WHITE_UP_QUEEN = "rnb1kbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"  # black missing queen
BLACK_UP_QUEEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNB1KBNR w KQkq - 0 1"  # white missing queen

EVALS = [classic_eval, tal_eval, karpov_eval, petrosian_eval]


@pytest.mark.parametrize("fn", EVALS)
def test_start_position_near_zero(fn):
    score = fn(chess.Board(START_FEN))
    assert -50 <= score <= 50, f"{fn.__module__}: start pos score {score} out of range"


@pytest.mark.parametrize("fn", EVALS)
def test_white_up_queen_positive(fn):
    score = fn(chess.Board(WHITE_UP_QUEEN))
    assert score > 200, f"{fn.__module__}: white up queen score {score} should be > 200"


@pytest.mark.parametrize("fn", EVALS)
def test_black_up_queen_negative(fn):
    score = fn(chess.Board(BLACK_UP_QUEEN))
    assert score < -200, f"{fn.__module__}: black up queen score {score} should be < -200"


@pytest.mark.parametrize("fn", EVALS)
def test_symmetry(fn):
    board = chess.Board(START_FEN)
    score = fn(board)
    assert abs(score) <= 50, f"{fn.__module__}: start pos not symmetric: {score}"
