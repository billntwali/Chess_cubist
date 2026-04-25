"""UCI smoke test — handshake, position, go → valid bestmove."""
import subprocess
import time
from pathlib import Path

from . import CheckResult

BINARY = Path(__file__).parents[2] / "core" / "target" / "release" / "chess_forge"
COMMANDS = "uci\nisready\nposition startpos\ngo movetime 500\nquit\n"


def run() -> CheckResult:
    start = time.time()

    if not BINARY.exists():
        return CheckResult("uci_check", False, "binary not found — run build_check first", (time.time() - start) * 1000)

    try:
        result = subprocess.run(
            [str(BINARY)],
            input=COMMANDS,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except subprocess.TimeoutExpired:
        return CheckResult("uci_check", False, "engine timed out after 15s", (time.time() - start) * 1000)
    except Exception as e:
        return CheckResult("uci_check", False, str(e), (time.time() - start) * 1000)

    output = result.stdout

    if "uciok" not in output:
        return CheckResult("uci_check", False, f"missing 'uciok'\noutput: {output[:300]}", (time.time() - start) * 1000)
    if "readyok" not in output:
        return CheckResult("uci_check", False, f"missing 'readyok'\noutput: {output[:300]}", (time.time() - start) * 1000)

    best_move = None
    for line in output.splitlines():
        if line.startswith("bestmove"):
            parts = line.split()
            if len(parts) >= 2:
                best_move = parts[1]
            break

    if not best_move or best_move == "0000":
        return CheckResult("uci_check", False, f"bad bestmove: {best_move!r}\noutput:\n{output[:400]}", (time.time() - start) * 1000)

    if not (4 <= len(best_move) <= 5 and best_move[:4].replace("0", "").isalnum()):
        return CheckResult("uci_check", False, f"malformed move: {best_move!r}", (time.time() - start) * 1000)

    return CheckResult("uci_check", True, f"bestmove {best_move}", (time.time() - start) * 1000, data={"move": best_move})
