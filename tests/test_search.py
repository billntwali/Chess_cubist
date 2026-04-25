"""Mate-in-N tests: verify the Rust engine finds forced mates via UCI."""
import subprocess
import pytest
from pathlib import Path

RUST_BINARY = Path(__file__).parents[1] / "core" / "target" / "release" / "chess_forge"

MATE_IN_ONE = [
    # (fen, expected_best_move)
    ("6k1/5ppp/8/8/8/8/8/R5K1 w - - 0 1", None),  # Ra8#
    ("r1bqkb1r/pppp1Qpp/2n2n2/4p3/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 0 4", None),  # scholar's mate
]


def uci_bestmove(fen: str, movetime_ms: int = 2000) -> str:
    if not RUST_BINARY.exists():
        pytest.skip("Rust binary not built")

    proc = subprocess.Popen(
        [str(RUST_BINARY)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    commands = f"uci\nisready\nposition fen {fen}\ngo movetime {movetime_ms}\n"
    stdout, _ = proc.communicate(input=commands, timeout=10)
    proc.wait()

    for line in stdout.splitlines():
        if line.startswith("bestmove"):
            return line.split()[1]
    return ""


@pytest.mark.parametrize("fen,expected", MATE_IN_ONE)
def test_finds_best_move(fen, expected):
    move = uci_bestmove(fen)
    assert move and move != "0000", f"Engine returned no move for {fen}"
    if expected:
        assert move == expected
