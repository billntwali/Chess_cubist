"""Tests for the eval generator's validation pipeline."""
import pytest
from eval import generator
from eval.generator import _quick_check, validate

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

SHADOWS_INT = """
def evaluate(board):
    int = 5
    return int(board.turn)
"""

MUTATES_BOARD_TURN = """
def evaluate(board):
    import chess
    board.turn = chess.BLACK
    return 0
"""

CALLS_PUSH = """
def evaluate(board):
    import chess
    board.push(chess.Move.null())
    board.pop()
    return 0
"""

TURN_BIASED_EVAL = """
def evaluate(board):
    import chess
    values = {
        chess.PAWN: 100,
        chess.KNIGHT: 320,
        chess.BISHOP: 330,
        chess.ROOK: 500,
        chess.QUEEN: 900,
    }
    score = 0
    for pt, val in values.items():
        score += val * len(board.pieces(pt, chess.WHITE))
        score -= val * len(board.pieces(pt, chess.BLACK))
    if board.turn == chess.BLACK:
        score -= 180
    return score
"""

START_BIASED_EVAL = """
def evaluate(board):
    import chess
    vals = {
        chess.PAWN: 100,
        chess.KNIGHT: 320,
        chess.BISHOP: 330,
        chess.ROOK: 500,
        chess.QUEEN: 900,
    }
    score = 0
    for pt, val in vals.items():
        score += val * len(board.pieces(pt, chess.WHITE))
        score += val * len(board.pieces(pt, chess.BLACK))
    return score
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


def test_builtin_shadowing_caught():
    ok, err = validate(SHADOWS_INT)
    assert not ok
    assert "built-in name" in err


def test_board_turn_mutation_caught():
    ok, err = validate(MUTATES_BOARD_TURN)
    assert not ok
    assert "mutate board attribute" in err


def test_mutating_board_methods_caught():
    ok, err = validate(CALLS_PUSH)
    assert not ok
    assert "mutating board method" in err


def test_turn_bias_caught():
    ok, err = validate(TURN_BIASED_EVAL)
    assert not ok
    assert "Perspective consistency" in err


def test_quick_check_catches_start_position_bias():
    err = _quick_check(START_BIASED_EVAL)
    assert err is not None
    assert "Sanity:" in err


def test_fallback_eval_is_valid():
    code = generator._fallback_eval_code("play like magnus carlsen", "Syntax error")
    ok, err = validate(code)
    assert ok, err


def _make_fake_client(response_text: str):
    """Build an OpenAI-style fake client returning response_text."""
    class FakeMessage:
        content = response_text
    class FakeChoice:
        message = FakeMessage()
    class FakeCompletion:
        choices = [FakeChoice()]
    class FakeCompletions:
        def create(self, **_kwargs):
            return FakeCompletion()
    class FakeChat:
        completions = FakeCompletions()
    class FakeClient:
        chat = FakeChat()
    return FakeClient()


def test_generate_falls_back_after_bad_output(monkeypatch):
    monkeypatch.setattr(generator, "_client", _make_fake_client("def evaluate(board):\nif True:\nreturn 0"))
    code = generator.generate("play like magnus carlsen", max_retries=1)
    ok, err = validate(code)
    assert ok, err
    assert "Fallback eval" in code


def test_generate_falls_back_after_api_error(monkeypatch):
    class FakeCompletions:
        def create(self, **_kwargs):
            raise TimeoutError("network timeout")
    class FakeChat:
        completions = FakeCompletions()
    class FakeClient:
        chat = FakeChat()
    monkeypatch.setattr(generator, "_client", FakeClient())
    code = generator.generate("play like magnus carlsen", max_retries=1)
    ok, err = validate(code)
    assert ok, err
    assert "Fallback eval" in code


def test_interpret_falls_back_after_api_error(monkeypatch):
    class FakeCompletions:
        def create(self, **_kwargs):
            raise TimeoutError("network timeout")
    class FakeChat:
        completions = FakeCompletions()
    class FakeClient:
        chat = FakeChat()
    monkeypatch.setattr(generator, "_client", FakeClient())
    interpreted = generator.interpret("play like magnus carlsen")
    assert "magnus" in interpreted.lower() or "positional" in interpreted.lower()


def test_fallback_interpretation_has_prompt_specific_styles():
    cases = {
        "play like magnus carlsen": "Magnus Carlsen",
        "play like a reckless attacker": "reckless attacker",
        "only move pawns if possible": "pawn-driven strategist",
        "play like a coward who avoids all trades": "defensively",
    }
    for prompt, expected in cases.items():
        assert expected in generator._fallback_interpretation(prompt)


def test_prompt_specific_fallback_evals_are_valid():
    prompts = [
        "play like magnus carlsen",
        "play like a reckless attacker",
        "only move pawns if possible",
        "play like a coward who avoids all trades",
    ]
    for prompt in prompts:
        interpreted = generator._fallback_interpretation(prompt)
        code = generator._fallback_eval_code(interpreted, "forced fallback")
        ok, err = validate(code)
        assert ok, f"{prompt}: {err}"
