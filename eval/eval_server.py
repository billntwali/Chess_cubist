"""Persistent eval bridge: Rust writes FEN lines, we return centipawn scores."""
import sys
import chess
import importlib.util


def load_eval(path: str):
    spec = importlib.util.spec_from_file_location("eval_fn", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.evaluate


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: eval_server.py <eval_path>", file=sys.stderr)
        sys.exit(1)

    evaluate = load_eval(sys.argv[1])

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        if line == "quit":
            break
        try:
            board = chess.Board(line)
            print(int(evaluate(board)), flush=True)
        except Exception as e:
            print(f"ERR {e}", flush=True)
