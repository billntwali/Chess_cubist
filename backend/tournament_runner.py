"""Round-robin tournament harness. Runs engines against each other via UCI subprocess."""
import asyncio
import json
import subprocess
import uuid
from pathlib import Path
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class TournamentRequest(BaseModel):
    engines: dict[str, str]  # {name: eval_file_path}
    games_per_pair: int = 10


@router.post("/tournament")
async def run_tournament_endpoint(request: TournamentRequest) -> dict:
    return await asyncio.to_thread(run_tournament, request.engines, request.games_per_pair)

RESULTS_DIR = Path(__file__).parents[1] / "tournament" / "results"
RUST_BINARY = Path(__file__).parents[1] / "core" / "target" / "release" / "chess_forge"
EVAL_SERVER = Path(__file__).parents[1] / "eval" / "eval_server.py"


def _spawn_engine(eval_path: str) -> subprocess.Popen:
    eval_cmd = f"python3 {EVAL_SERVER} {eval_path}"
    proc = subprocess.Popen(
        [str(RUST_BINARY), "--eval-server", eval_cmd],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    _uci_init(proc)
    return proc


def _uci_init(proc: subprocess.Popen):
    proc.stdin.write("uci\n"); proc.stdin.flush()
    _read_until(proc, "uciok")
    proc.stdin.write("isready\n"); proc.stdin.flush()
    _read_until(proc, "readyok")


def _read_until(proc: subprocess.Popen, token: str) -> list[str]:
    lines = []
    while True:
        line = proc.stdout.readline().strip()
        lines.append(line)
        if line == token:
            return lines


MAX_GAME_MOVES = 150  # hard cap to prevent runaway games

def _play_game(
    white_path: str,
    black_path: str,
    movetime_ms: int = 500,
    search_depth: int = 2,
) -> str:
    """Play one game, return 'white' | 'black' | 'draw'."""
    import chess
    white = _spawn_engine(white_path)
    black = _spawn_engine(black_path)
    board = chess.Board()
    moves = []

    try:
        while not board.is_game_over(claim_draw=True) and len(moves) < MAX_GAME_MOVES:
            engine = white if board.turn == chess.WHITE else black
            pos_cmd = "position startpos" + (" moves " + " ".join(moves) if moves else "")
            engine.stdin.write(pos_cmd + "\n")
            engine.stdin.write(f"go movetime {movetime_ms} depth {search_depth}\n")
            engine.stdin.flush()

            best_move = ""
            while True:
                line = engine.stdout.readline()
                if not line:  # EOF — engine process died
                    break
                line = line.strip()
                if line.startswith("bestmove"):
                    best_move = line.split()[1]
                    break

            if not best_move or best_move == "0000":
                break

            try:
                board.push_uci(best_move)
                moves.append(best_move)
            except Exception:
                break
    finally:
        for p in (white, black):
            try:
                p.stdin.write("quit\n"); p.stdin.flush(); p.wait(timeout=3)
            except Exception:
                p.kill()

    result = board.result()
    if result == "1-0":
        return "white"
    elif result == "0-1":
        return "black"
    return "draw"


def run_tournament(
    engine_paths: dict[str, str],
    games_per_pair: int = 10,
    movetime_ms: int = 500,
    search_depth: int = 2,
) -> dict:
    """Run a round-robin tournament.

    Args:
        engine_paths: {name: eval_file_path}
        games_per_pair: number of games per matchup (split evenly as white/black)
        movetime_ms: milliseconds per move (lower = faster games for demos)
        search_depth: fixed UCI search depth for each tournament move
    Returns:
        standings dict with W/D/L per engine
    """
    names = list(engine_paths.keys())
    standings = {n: {"W": 0, "D": 0, "L": 0} for n in names}
    matchups = []

    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            a, b = names[i], names[j]
            for g in range(games_per_pair):
                white_name, black_name = (a, b) if g % 2 == 0 else (b, a)
                result = _play_game(
                    engine_paths[white_name],
                    engine_paths[black_name],
                    movetime_ms=movetime_ms,
                    search_depth=search_depth,
                )
                if result == "white":
                    standings[white_name]["W"] += 1
                    standings[black_name]["L"] += 1
                elif result == "black":
                    standings[black_name]["W"] += 1
                    standings[white_name]["L"] += 1
                else:
                    standings[white_name]["D"] += 1
                    standings[black_name]["D"] += 1
                matchups.append({"white": white_name, "black": black_name, "result": result})

    session_id = uuid.uuid4().hex[:8]
    output = {
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "standings": standings,
        "matchups": matchups,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / f"{session_id}.json", "w") as f:
        json.dump(output, f, indent=2)

    return output
