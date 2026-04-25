"""Verify the Rust binary exists, or build it."""
import subprocess
import time
from pathlib import Path

from . import CheckResult

REPO = Path(__file__).parents[2]
BINARY = REPO / "core" / "target" / "release" / "chess_forge"
CORE_DIR = REPO / "core"


def run(no_build: bool = False) -> CheckResult:
    start = time.time()

    if BINARY.exists():
        return CheckResult(
            "build_check", True,
            f"binary found",
            (time.time() - start) * 1000,
        )

    if no_build:
        return CheckResult(
            "build_check", False,
            f"binary not found at {BINARY} and --no-build set",
            (time.time() - start) * 1000,
        )

    result = subprocess.run(
        ["cargo", "build", "--release"],
        cwd=str(CORE_DIR),
        capture_output=True,
        text=True,
    )

    if result.returncode == 0 and BINARY.exists():
        return CheckResult("build_check", True, "compiled successfully", (time.time() - start) * 1000)

    stderr_tail = result.stderr[-400:].strip()
    return CheckResult("build_check", False, f"cargo build failed:\n{stderr_tail}", (time.time() - start) * 1000)
