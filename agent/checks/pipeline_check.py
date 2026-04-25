"""Full pipeline: play 3 games between personalities via Rust engine + eval server."""
import subprocess
import time
from pathlib import Path

import chess

from . import CheckResult

REPO = Path(__file__).parents[2]
BINARY = REPO / "core" / "target" / "release" / "chess_forge"
EVAL_SERVER = REPO / "eval" / "eval_server.py"

CLASSIC   = REPO / "eval" / "classic.py"
TAL       = REPO / "eval" / "personalities" / "tal.py"
KARPOV    = REPO / "eval" / "personalities" / "karpov.py"
PETROSIAN = REPO / "eval" / "personalities" / "petrosian.py"

MOVETIME_MS = 50   # fast enough for CI; eval server adds ~0.5s per move anyway
MAX_MOVES   = 40   # 40 half-moves (~20 full moves) caps each game at ~30s


def _spawn(eval_path: str) -> subprocess.Popen:
    eval_cmd = f"python3 {EVAL_SERVER} {eval_path}"
    proc = subprocess.Popen(
        [str(BINARY), "--eval-server", eval_cmd],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    _uci_init(proc)
    return proc


def _uci_init(proc: subprocess.Popen):
    proc.stdin.write("uci\n"); proc.stdin.flush()
    _read_until(proc, "uciok", timeout_lines=20)
    proc.stdin.write("isready\n"); proc.stdin.flush()
    _read_until(proc, "readyok", timeout_lines=20)


def _read_until(proc: subprocess.Popen, token: str, timeout_lines: int = 100):
    for _ in range(timeout_lines):
        line = proc.stdout.readline().strip()
        if line == token:
            return
    raise RuntimeError(f"never received '{token}'")


def _get_move(proc: subprocess.Popen, moves: list[str]) -> str | None:
    pos_cmd = "position startpos" + (" moves " + " ".join(moves) if moves else "")
    proc.stdin.write(pos_cmd + "\n")
    proc.stdin.write(f"go movetime {MOVETIME_MS}\n")
    proc.stdin.flush()
    for _ in range(500):
        line = proc.stdout.readline().strip()
        if line.startswith("bestmove"):
            parts = line.split()
            return parts[1] if len(parts) >= 2 else None
    return None


def _quit(proc: subprocess.Popen):
    try:
        proc.stdin.write("quit\n"); proc.stdin.flush()
        proc.wait(timeout=3)
    except Exception:
        proc.kill()


def _play_game(white_path: str, black_path: str) -> str:
    """Return 'white' | 'black' | 'draw'."""
    white = _spawn(white_path)
    black = _spawn(black_path)
    board = chess.Board()
    moves: list[str] = []
    try:
        while not board.is_game_over(claim_draw=True) and len(moves) < MAX_MOVES:
            engine = white if board.turn == chess.WHITE else black
            mv_uci = _get_move(engine, moves)
            if not mv_uci or mv_uci == "0000":
                break
            try:
                board.push_uci(mv_uci)
                moves.append(mv_uci)
            except ValueError:
                break
    finally:
        _quit(white)
        _quit(black)

    result = board.result(claim_draw=True)
    if result == "1-0": return "white"
    if result == "0-1": return "black"
    return "draw"


def run(generated_eval_path: str | None = None) -> CheckResult:
    start = time.time()

    if not BINARY.exists():
        return CheckResult("pipeline_check", False, "binary not found — run build_check first", (time.time() - start) * 1000)

    user_eval = str(generated_eval_path) if generated_eval_path else str(CLASSIC)
    user_label = "generated" if generated_eval_path else "classic"

    matchups = [
        (user_label, user_eval,    "tal",      str(TAL)),
        ("karpov",   str(KARPOV),  user_label, user_eval),
        ("tal",      str(TAL),     "petrosian",str(PETROSIAN)),
    ]

    games = []
    for white_name, white_path, black_name, black_path in matchups:
        try:
            outcome = _play_game(white_path, black_path)
            games.append({"white": white_name, "black": black_name, "result": outcome})
        except Exception as e:
            return CheckResult(
                "pipeline_check", False,
                f"{white_name} vs {black_name} crashed: {e}",
                (time.time() - start) * 1000,
                data={"games": games},
            )

    details = "  |  ".join(
        f"{g['white']} vs {g['black']}: {g['result']}" for g in games
    )
    return CheckResult("pipeline_check", True, details, (time.time() - start) * 1000, data={"games": games})
