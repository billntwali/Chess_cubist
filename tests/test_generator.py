"""Tests for the eval generator's 5-gate validation pipeline."""
import pytest
from eval import generator
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


def test_fallback_eval_is_valid():
    code = generator._fallback_eval_code("play like magnus carlsen", "Syntax error")
    ok, err = validate(code)
    assert ok, err


def test_generate_falls_back_after_malformed_claude(monkeypatch):
    class FakeMessage:
        stop_reason = "end_turn"
        content = [type("Content", (), {"text": "def evaluate(board):\nif True:\nreturn 0"})()]

    class FakeMessages:
        def create(self, **_kwargs):
            return FakeMessage()

    class FakeClient:
        messages = FakeMessages()

    monkeypatch.setattr(generator, "_client", FakeClient())

    code = generator.generate("play like magnus carlsen", max_retries=1)
    ok, err = validate(code)

    assert ok, err
    assert "Fallback eval" in code


def test_generate_falls_back_after_truncated_claude(monkeypatch):
    class FakeMessage:
        stop_reason = "max_tokens"
        content = [type("Content", (), {"text": "def evaluate(board):\n    if True:"})()]

    class FakeMessages:
        def create(self, **_kwargs):
            return FakeMessage()

    class FakeClient:
        messages = FakeMessages()

    monkeypatch.setattr(generator, "_client", FakeClient())

    code = generator.generate("play like magnus carlsen", max_retries=0)
    ok, err = validate(code)

    assert ok, err
    assert "Fallback eval" in code


def test_generate_falls_back_after_api_error(monkeypatch):
    class FakeMessages:
        def create(self, **_kwargs):
            raise TimeoutError("network timeout")

    class FakeClient:
        messages = FakeMessages()

    monkeypatch.setattr(generator, "_client", FakeClient())

    code = generator.generate("play like magnus carlsen", max_retries=1)
    ok, err = validate(code)

    assert ok, err
    assert "Fallback eval" in code


def test_interpret_falls_back_after_api_error(monkeypatch):
    class FakeMessages:
        def create(self, **_kwargs):
            raise TimeoutError("network timeout")

    class FakeClient:
        messages = FakeMessages()

    monkeypatch.setattr(generator, "_client", FakeClient())

    interpreted = generator.interpret("play like magnus carlsen")

    assert "magnus carlsen" in interpreted.lower()
    assert "positional advantages" in interpreted


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
