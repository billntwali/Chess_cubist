"""Benchmark classic.py against Stockfish at a given Skill Level."""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parents[1]
BINARY = ROOT / "core" / "target" / "release" / "chess_forge"
EVAL_SERVER = ROOT / "eval" / "eval_server.py"
CLASSIC = ROOT / "eval" / "classic.py"


def run_bench(skill_level: int = 5, games: int = 10, movetime_ms: int = 200) -> dict:
    try:
        import chess
        import chess.engine
    except ImportError:
        sys.exit("ERROR: python-chess not installed. Run: pip install chess")

    eval_cmd = f"python {EVAL_SERVER} {CLASSIC}"
    W = D = L = 0

    print(f"Benchmarking classic.py vs Stockfish Skill {skill_level} ({games} games)...")

    sf = chess.engine.SimpleEngine.popen_uci("stockfish")
    sf.configure({"Skill Level": skill_level})

    for game_num in range(games):
        our_color = chess.WHITE if game_num % 2 == 0 else chess.BLACK
        our_proc = subprocess.Popen(
            [str(BINARY), "--eval-server", eval_cmd],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )

        # UCI handshake
        our_proc.stdin.write("uci\n")
        our_proc.stdin.flush()
        while True:
            if our_proc.stdout.readline().strip() == "uciok":
                break
        our_proc.stdin.write("isready\n")
        our_proc.stdin.flush()
        while True:
            if our_proc.stdout.readline().strip() == "readyok":
                break

        board = chess.Board()
        moves: list[str] = []

        while not board.is_game_over(claim_draw=True):
            if board.turn == our_color:
                pos = "position startpos" + (" moves " + " ".join(moves) if moves else "")
                our_proc.stdin.write(pos + "\n")
                our_proc.stdin.write(f"go movetime {movetime_ms}\n")
                our_proc.stdin.flush()
                line = ""
                while not line.startswith("bestmove"):
                    line = our_proc.stdout.readline().strip()
                mv = line.split()[1]
            else:
                result = sf.play(board, chess.engine.Limit(time=movetime_ms / 1000))
                mv = result.move.uci()

            try:
                board.push_uci(mv)
                moves.append(mv)
            except Exception:
                break

        our_proc.stdin.write("quit\n")
        our_proc.stdin.flush()
        our_proc.wait(timeout=5)

        r = board.result()
        our_label = "W" if our_color == chess.WHITE else "B"
        if (r == "1-0" and our_color == chess.WHITE) or (r == "0-1" and our_color == chess.BLACK):
            W += 1
            outcome = "WIN"
        elif r == "1/2-1/2":
            D += 1
            outcome = "DRAW"
        else:
            L += 1
            outcome = "LOSS"
        print(f"  Game {game_num + 1:2d}: {r}  (our color: {our_label})  → {outcome}")

    sf.quit()
    print(f"\nResult vs Stockfish Skill {skill_level}: {W}W / {D}D / {L}L  ({games} games)")
    return {"W": W, "D": D, "L": L, "skill_level": skill_level, "games": games}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark chess_forge vs Stockfish")
    parser.add_argument("--skill", type=int, default=5, help="Stockfish Skill Level (0-20)")
    parser.add_argument("--games", type=int, default=10, help="Number of games")
    parser.add_argument("--movetime", type=int, default=200, help="Milliseconds per move")
    args = parser.parse_args()

    if not BINARY.exists():
        sys.exit(f"ERROR: Rust binary not found at {BINARY}. Run: make build")

    run_bench(skill_level=args.skill, games=args.games, movetime_ms=args.movetime)
