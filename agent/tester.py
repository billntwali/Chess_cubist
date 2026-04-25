#!/usr/bin/env python3
"""
Chess Forge — Full Pipeline Tester

Runs five checks in sequence:
  1. build_check      — Rust binary present / cargo build
  2. eval_check       — eval_server.py standalone for all personalities
  3. generator_check  — Claude API → eval function → 5-gate validation
  4. uci_check        — UCI handshake + bestmove smoke test
  5. pipeline_check   — 3 live games between personalities

Usage:
  python agent/tester.py                 # run all checks
  python agent/tester.py --only uci      # run one check
  python agent/tester.py --no-build      # skip cargo build if binary missing
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# Make repo root importable
sys.path.insert(0, str(Path(__file__).parents[1]))

from agent.checks import CheckResult  # noqa: E402
from agent.checks import (  # noqa: E402
    build_check,
    eval_check,
    generator_check,
    pipeline_check,
    uci_check,
)

GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

CHECKS = {
    "build":     build_check,
    "eval":      eval_check,
    "generator": generator_check,
    "uci":       uci_check,
    "pipeline":  pipeline_check,
}


def _icon(result: CheckResult) -> str:
    if result.data.get("skipped"):
        return f"{YELLOW}~{RESET}"
    return f"{GREEN}✓{RESET}" if result.passed else f"{RED}✗{RESET}"


def _fmt(i: int, total: int, result: CheckResult) -> str:
    return (
        f"  [{i}/{total}] {result.name:<20} {_icon(result)}"
        f"  {result.details}"
        f"  {YELLOW}({result.duration_ms:.0f}ms){RESET}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Chess Forge pipeline tester")
    parser.add_argument("--only", choices=list(CHECKS.keys()), metavar="CHECK",
                        help=f"Run a single check: {', '.join(CHECKS)}")
    parser.add_argument("--no-build", action="store_true",
                        help="Fail instead of running cargo build if binary is missing")
    args = parser.parse_args()

    to_run = {args.only: CHECKS[args.only]} if args.only else CHECKS
    total  = len(to_run)
    results: list[CheckResult] = []
    generated_eval_path: Optional[str] = None

    print(f"\n{BOLD}Chess Forge Pipeline Tester{RESET}  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    for i, (name, module) in enumerate(to_run.items(), 1):
        # Dispatch with check-specific kwargs
        if name == "build":
            result = module.run(no_build=args.no_build)
        elif name == "pipeline":
            result = module.run(generated_eval_path=generated_eval_path)
        else:
            result = module.run()

        # Thread generated eval path into pipeline_check
        if name == "generator" and result.passed and not result.data.get("skipped"):
            generated_eval_path = result.data.get("eval_path")

        print(_fmt(i, total, result))

        # Print failure detail on next line
        if not result.passed and not result.data.get("skipped"):
            for line in result.details.splitlines():
                print(f"        {RED}{line}{RESET}")

        results.append(result)

    # Summary
    passed  = sum(1 for r in results if r.passed)
    skipped = sum(1 for r in results if r.data.get("skipped"))
    failed  = total - passed
    print(f"\n  {'─' * 48}")
    if failed == 0:
        suffix = f"  ({skipped} skipped)" if skipped else ""
        print(f"  {GREEN}{BOLD}{passed}/{total} passed{RESET}{suffix}")
    else:
        print(f"  {RED}{BOLD}{failed}/{total} failed{RESET}  ({passed} passed, {skipped} skipped)")

    # Save JSON report
    results_dir = Path(__file__).parent / "results"
    results_dir.mkdir(exist_ok=True)
    report_path = results_dir / f"{datetime.now().strftime('%Y-%m-%dT%H-%M-%S')}.json"
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {"total": total, "passed": passed, "failed": failed, "skipped": skipped},
        "checks": [
            {
                "name":        r.name,
                "passed":      r.passed,
                "details":     r.details,
                "duration_ms": round(r.duration_ms),
                **r.data,
            }
            for r in results
        ],
    }
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    print(f"\n  report → {report_path}\n")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
