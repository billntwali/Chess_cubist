"""Test the Claude eval generator pipeline — interpret → generate → all 5 gates."""
import os
import sys
import time
from pathlib import Path

from . import CheckResult

REPO = Path(__file__).parents[2]
TEST_PHILOSOPHY = "a cowardly engine that avoids all trades and retreats pieces"


def run() -> CheckResult:
    start = time.time()

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return CheckResult(
            "generator_check", True,
            "SKIPPED — ANTHROPIC_API_KEY not set",
            (time.time() - start) * 1000,
            data={"skipped": True},
        )

    sys.path.insert(0, str(REPO))
    try:
        from eval.generator import interpret, generate, validate, save_eval
    except ImportError as e:
        return CheckResult("generator_check", False, f"import error: {e}", (time.time() - start) * 1000)

    try:
        interpreted = interpret(TEST_PHILOSOPHY)
    except Exception as e:
        return CheckResult("generator_check", False, f"interpret() failed: {e}", (time.time() - start) * 1000)

    try:
        code = generate(interpreted)
    except Exception as e:
        return CheckResult("generator_check", False, f"generate() failed: {e}", (time.time() - start) * 1000)

    ok, err = validate(code)
    if not ok:
        return CheckResult(
            "generator_check", False,
            f"validation failed — {err}",
            (time.time() - start) * 1000,
            data={"interpreted": interpreted, "validation_error": err},
        )

    # Save the generated eval so pipeline_check can use it
    try:
        eval_path = save_eval(code, "tester_agent_cowardly")
    except Exception as e:
        eval_path = None

    return CheckResult(
        "generator_check", True,
        f'all 5 gates passed — "{interpreted[:80]}"',
        (time.time() - start) * 1000,
        data={"interpreted": interpreted, "eval_path": eval_path},
    )
