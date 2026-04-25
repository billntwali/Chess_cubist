"""Tests for the round-robin tournament harness — bracket math and output correctness."""
import json
import math
from pathlib import Path
from unittest.mock import patch

import pytest

from backend.tournament_runner import run_tournament


def _cycle(results):
    """Infinite cycler over a fixed result sequence."""
    i = 0
    while True:
        yield results[i % len(results)]
        i += 1


def _mock_results(sequence):
    gen = _cycle(sequence)
    return lambda *_args, **_kwargs: next(gen)


# --- bracket math ---

def test_two_engines_game_count(tmp_path):
    """2 engines × 4 games_per_pair = 4 total games."""
    calls = []
    def fake_play(w, b, **kw):
        calls.append((w, b))
        return "white"

    with patch("backend.tournament_runner._play_game", side_effect=fake_play):
        with patch("backend.tournament_runner.RESULTS_DIR", tmp_path):
            run_tournament({"A": "a.py", "B": "b.py"}, games_per_pair=4)

    assert len(calls) == 4


def test_four_engines_game_count(tmp_path):
    """4 engines → C(4,2)=6 pairings × 10 games = 60 total games."""
    calls = []
    def fake_play(w, b, **kw):
        calls.append((w, b))
        return "draw"

    with patch("backend.tournament_runner._play_game", side_effect=fake_play):
        with patch("backend.tournament_runner.RESULTS_DIR", tmp_path):
            run_tournament({"A": "a.py", "B": "b.py", "C": "c.py", "D": "d.py"}, games_per_pair=10)

    expected = math.comb(4, 2) * 10
    assert len(calls) == expected


def test_color_alternation(tmp_path):
    """Each engine plays exactly half its games as white, half as black per pairing."""
    white_as_a = []
    def fake_play(w, b, **kw):
        white_as_a.append(w == "a.py")
        return "draw"

    with patch("backend.tournament_runner._play_game", side_effect=fake_play):
        with patch("backend.tournament_runner.RESULTS_DIR", tmp_path):
            run_tournament({"A": "a.py", "B": "b.py"}, games_per_pair=6)

    # 3 games as white, 3 as black
    assert sum(white_as_a) == 3
    assert white_as_a.count(False) == 3


# --- W/D/L accounting ---

def test_wdl_totals_sum_correctly(tmp_path):
    """Total W+D+L per engine must equal total games played."""
    with patch("backend.tournament_runner._play_game", return_value="white"):
        with patch("backend.tournament_runner.RESULTS_DIR", tmp_path):
            result = run_tournament(
                {"A": "a.py", "B": "b.py", "C": "c.py"},
                games_per_pair=4,
            )

    names = list(result["standings"].keys())
    for name in names:
        s = result["standings"][name]
        assert s["W"] + s["D"] + s["L"] == 2 * 4  # 2 opponents × 4 games each


def test_wins_and_losses_mirror(tmp_path):
    """Every white win for one engine is a loss for the other."""
    with patch("backend.tournament_runner._play_game", return_value="white"):
        with patch("backend.tournament_runner.RESULTS_DIR", tmp_path):
            result = run_tournament({"A": "a.py", "B": "b.py"}, games_per_pair=4)

    total_wins = sum(s["W"] for s in result["standings"].values())
    total_losses = sum(s["L"] for s in result["standings"].values())
    assert total_wins == total_losses


def test_draws_are_symmetric(tmp_path):
    """Each draw increments both engines' draw count."""
    with patch("backend.tournament_runner._play_game", return_value="draw"):
        with patch("backend.tournament_runner.RESULTS_DIR", tmp_path):
            result = run_tournament({"A": "a.py", "B": "b.py"}, games_per_pair=4)

    for s in result["standings"].values():
        assert s["D"] == 4
        assert s["W"] == 0
        assert s["L"] == 0


# --- JSON output ---

def test_json_file_written(tmp_path):
    """run_tournament writes a JSON file to results dir."""
    with patch("backend.tournament_runner._play_game", return_value="draw"):
        with patch("backend.tournament_runner.RESULTS_DIR", tmp_path):
            result = run_tournament({"A": "a.py", "B": "b.py"}, games_per_pair=2)

    files = list(tmp_path.glob("*.json"))
    assert len(files) == 1
    saved = json.loads(files[0].read_text())
    assert saved["session_id"] == result["session_id"]
    assert "standings" in saved
    assert "matchups" in saved


def test_session_ids_are_unique(tmp_path):
    """Each tournament run produces a distinct session_id."""
    ids = set()
    for _ in range(3):
        with patch("backend.tournament_runner._play_game", return_value="draw"):
            with patch("backend.tournament_runner.RESULTS_DIR", tmp_path):
                result = run_tournament({"A": "a.py", "B": "b.py"}, games_per_pair=1)
        ids.add(result["session_id"])
    assert len(ids) == 3


def test_matchups_recorded(tmp_path):
    """Every game is recorded in the matchups list."""
    with patch("backend.tournament_runner._play_game", return_value="white"):
        with patch("backend.tournament_runner.RESULTS_DIR", tmp_path):
            result = run_tournament({"A": "a.py", "B": "b.py"}, games_per_pair=6)

    assert len(result["matchups"]) == 6
    for m in result["matchups"]:
        assert m["result"] in ("white", "black", "draw")
        assert "white" in m and "black" in m
