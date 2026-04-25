# Testing Notes

This document records the testing performed around generated evaluation functions, the `"play like magnus carlsen"` failure, and tournament execution.

## Summary

The generator previously allowed malformed Claude output to reach the UI after retries were exhausted. The concrete failure was:

```text
Syntax error: expected an indented block (<unknown>, line 313)
```

This happened while testing a normal user prompt:

```text
play like magnus carlsen
```

The failure was not caused by the saved source files. It came from raw Claude-generated Python being parsed by the validator.

## Root Cause

The generation pipeline had this behavior:

1. Claude generated an `evaluate(board)` function.
2. The app ran a quick syntax/runtime check.
3. If Claude kept returning invalid code after the retry limit, `generate()` returned the last malformed response.
4. The backend then surfaced the validator error to the UI.

For the Magnus prompt, Claude produced an overlong function with invalid syntax. In one reproduction, the generated function was more than 300 lines and failed with:

```text
Syntax error: invalid syntax (<unknown>, line 306)
```

Another observed user-facing error was:

```text
Syntax error: expected an indented block (<unknown>, line 313)
```

## Fixes Made

The generator was hardened so malformed Python should no longer reach the UI.

Changes in `eval/generator.py`:

- Claude client now has a 30 second timeout.
- The codegen prompt now asks for:
  - complete indented blocks
  - no placeholders or TODOs
  - functions under 180 lines
  - simpler loops and constants instead of deeply nested logic
- `generate()` now runs the full validator on each Claude response.
- If Claude returns invalid code after retries, `generate()` returns a valid fallback eval.
- If Claude response is truncated at the token limit, `generate()` returns a valid fallback eval.
- If the Claude API times out or errors, `generate()` returns a valid fallback eval.
- `interpret()` also has a local fallback if the interpretation API call fails.
- Fallback interpretations are prompt-aware for common demo inputs:
  - Magnus/Carlsen
  - reckless attacker
  - pawn-focused play
  - coward/defensive/trade-avoidant play

Changes in `tests/test_generator.py`:

- Added coverage for fallback eval validity.
- Added coverage for malformed Claude output.
- Added coverage for truncated Claude output.
- Added coverage for Claude/API errors.
- Added coverage for interpretation fallback.
- Added coverage for prompt-specific fallback styles.

## Exact Prompt Test

Prompt tested:

```text
play like magnus carlsen
```

Live generation result after the fix:

```text
VALID True
FALLBACK False
LINES 218
PATH /Users/joongwonahn/Documents/Chess_cubist/eval/generated/a4a9ed3e_Magnus_hunts_for_the_smallest_po.py
```

This means Claude successfully generated a valid native eval function for the exact prompt, without needing fallback.

## Prompt Sweep

The following prompts were tested:

```text
play like magnus carlsen
play like a reckless attacker
only move pawns if possible
play like a coward who avoids all trades
```

Result:

- All prompts produced valid eval code.
- Some calls used fallback because the Claude API was slow or unavailable.
- Fallback evals were still prompt-specific and passed validation.

Saved fallback eval files:

```text
eval/generated/28c7671c_Plays_like_Magnus_Carlsen_by_rew.py
eval/generated/437c3e03_Plays_as_a_reckless_attacker_by_.py
eval/generated/29d42a6c_Plays_as_a_pawn-driven_strategis.py
eval/generated/b1d938a2_Plays_defensively_by_rewarding_k.py
```

## Tournament Tests

### Generated Magnus Tournament

The generated Magnus eval was entered into a quick tournament against the built-in personalities.

Command shape:

```bash
python3 -u - <<'PY'
from backend.tournament_runner import run_tournament

eval_path = "/Users/joongwonahn/Documents/Chess_cubist/eval/generated/a4a9ed3e_Magnus_hunts_for_the_smallest_po.py"
r = run_tournament(
    {
        "Magnus": eval_path,
        "Tal": "eval/personalities/tal.py",
        "Karpov": "eval/personalities/karpov.py",
        "Petrosian": "eval/personalities/petrosian.py",
    },
    games_per_pair=1,
    movetime_ms=50,
    search_depth=2,
)
print(r)
PY
```

Result:

```text
session_id: f348a6bd
Magnus:   2W / 0D / 1L
Tal:      1W / 0D / 2L
Karpov:   2W / 0D / 1L
Petrosian:1W / 0D / 2L
```

### Fallback Style Tournament

Fallback-generated styles were also run through a small tournament.

Engines:

- `MagnusFallback`
- `RecklessFallback`
- `PawnFallback`
- `CowardFallback`

Result:

```text
session_id: e190f3e6
MagnusFallback:    2W / 0D / 1L
RecklessFallback:  2W / 0D / 1L
PawnFallback:      1W / 1D / 1L
CowardFallback:    0W / 1D / 2L
```

## Automated Test Results

Generator tests:

```bash
python3 -m pytest tests/test_generator.py -v
```

Result:

```text
12 passed
```

Tournament tests:

```bash
python3 -m pytest tests/test_tournament.py -v
```

Result:

```text
9 passed
```

Note: pytest emitted a cache warning in this environment because the sandbox could not write `.pytest_cache` metadata. The tests themselves passed.

## Manual Smoke Commands

Run generator tests:

```bash
python3 -m pytest tests/test_generator.py -v
```

Run tournament tests:

```bash
python3 -m pytest tests/test_tournament.py -v
```

Run a small tournament manually:

```bash
python3 -u - <<'PY'
from backend.tournament_runner import run_tournament

r = run_tournament(
    {
        "Classic": "eval/classic.py",
        "Tal": "eval/personalities/tal.py",
        "Karpov": "eval/personalities/karpov.py",
        "Petrosian": "eval/personalities/petrosian.py",
    },
    games_per_pair=1,
    movetime_ms=50,
    search_depth=2,
)
print(r)
PY
```

Run the full configured tournament:

```bash
make tournament
```

The full tournament uses more games and may take noticeably longer than the UI smoke path.

## Current Confidence

The generator now has guardrails for the failure classes observed during testing:

- malformed Python
- incomplete indentation
- truncated Claude output
- API timeout or interruption
- generic fallback behavior that ignores the user's prompt

The tournament runner also accepts generated eval files end to end and saves JSON results successfully.
