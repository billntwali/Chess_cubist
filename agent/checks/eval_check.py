"""Test each eval personality standalone via eval_server.py."""
import subprocess
import time
from pathlib import Path

from . import CheckResult

REPO = Path(__file__).parents[2]
EVAL_SERVER = REPO / "eval" / "eval_server.py"
START_FEN = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

PERSONALITIES = {
    "classic":   REPO / "eval" / "classic.py",
    "tal":       REPO / "eval" / "personalities" / "tal.py",
    "karpov":    REPO / "eval" / "personalities" / "karpov.py",
    "petrosian": REPO / "eval" / "personalities" / "petrosian.py",
}


def run() -> CheckResult:
    start = time.time()
    scores = {}

    for name, path in PERSONALITIES.items():
        if not path.exists():
            return CheckResult("eval_check", False, f"{name}: file not found at {path}", (time.time() - start) * 1000)
        try:
            proc = subprocess.run(
                ["python3", str(EVAL_SERVER), str(path)],
                input=f"{START_FEN}\nquit\n",
                capture_output=True,
                text=True,
                timeout=10,
            )
            first_line = proc.stdout.strip().split("\n")[0] if proc.stdout.strip() else ""
            if first_line.startswith("ERR"):
                return CheckResult("eval_check", False, f"{name}: server error — {first_line}", (time.time() - start) * 1000)
            score = int(first_line)
            if not (-500 <= score <= 500):
                return CheckResult("eval_check", False, f"{name}: score {score}cp out of expected range ±500", (time.time() - start) * 1000)
            scores[name] = score
        except subprocess.TimeoutExpired:
            return CheckResult("eval_check", False, f"{name}: timed out", (time.time() - start) * 1000)
        except (ValueError, IndexError) as e:
            return CheckResult("eval_check", False, f"{name}: could not parse score — {e}", (time.time() - start) * 1000)
        except Exception as e:
            return CheckResult("eval_check", False, f"{name}: {e}", (time.time() - start) * 1000)

    details = "  ".join(f"{k}={v:+d}cp" for k, v in scores.items())
    return CheckResult("eval_check", True, details, (time.time() - start) * 1000, data={"scores": scores})
