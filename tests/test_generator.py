"""Tests for the eval generator's 5-gate validation pipeline."""
import pytest
from eval.generator import validate

VALID_EVAL = """
def evaluate(board):
    import chess
    score = 0
    for pt in [chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN]:
        vals = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 330, chess.ROOK: 500, chess.QUEEN: 900}
        score += vals[pt] * len(board.pieces(pt, chess.WHITE))
        score -= vals[pt] * len(board.pieces(pt, chess.BLACK))
    return score
"""

SYNTAX_ERROR = "def evaluate(board) return 0"

BANNED_IMPORT = """
import os
def evaluate(board):
    return 0
"""

CONSTANT_EVAL = """
def evaluate(board):
    return 0
"""

RANDOM_EVAL = """
import random
def evaluate(board):
    return random.randint(-100, 100)
"""


def test_valid_eval_passes():
    ok, err = validate(VALID_EVAL)
    assert ok, err


def test_syntax_error_caught():
    ok, err = validate(SYNTAX_ERROR)
    assert not ok
    assert "Syntax" in err


def test_banned_import_caught():
    ok, err = validate(BANNED_IMPORT)
    assert not ok
    assert "Safety" in err or "banned" in err.lower()


def test_constant_eval_caught():
    ok, err = validate(CONSTANT_EVAL)
    assert not ok


def test_random_banned():
    ok, err = validate(RANDOM_EVAL)
    assert not ok
