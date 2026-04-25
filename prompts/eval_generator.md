# Eval Generator Prompts

Used in `eval/generator.py`. Document every iteration here — judges evaluate prompt engineering process.

---

## Step 1 — Interpretation Prompt

**Purpose:** Map the user's natural language description to a chess-expressible position evaluation concept.
**Model:** `claude-haiku-4-5` (fast, cheap — shown to user before codegen)

```
The user wants a chess engine with this philosophy: "{description}"

Restate this as a concrete chess POSITION evaluation strategy in one sentence —
something expressible as: "score this board state highly when [X]."

Use only chess concepts: piece activity, king safety, pawn structure, material
balance, mobility, open files, outposts, etc.

If the input describes a move rule (e.g. "only move pawns"): redirect to the
closest positional philosophy and prefix with:
"Note: your input was a move rule — here's the closest positional equivalent:"

Return ONLY the one-sentence restatement.
```

### Iteration notes

| Version | Change | Reason |
|---------|--------|--------|
| v1 | Initial prompt | — |

---

## Step 2 — Codegen Prompt

**Purpose:** Generate a valid, safe, deterministic Python `evaluate(board)` function.
**Model:** `claude-sonnet-4-6` (more capable — generates the actual eval code)

```
You are a chess engine programmer. Write a Python function:

    def evaluate(board: chess.Board) -> int

returning a centipawn score from White's perspective (positive = White better).

Philosophy: {interpreted_description}

Hard rules:
- Import only: chess, math
- No random, time, network, file I/O, or side effects
- Must not raise exceptions on any legal board state
- Deterministic — same board always returns same score
- Return an integer
- Return ONLY the function, no explanation

Material: pawn=100, knight=320, bishop=330, rook=500, queen=900
```

### Iteration notes

| Version | Change | Reason |
|---------|--------|--------|
| v1 | Initial prompt | — |

---

## Example Interpretations

| User input | Interpreted as |
|-----------|---------------|
| "plays like Tal" | Maximizes piece activity and bonuses for pieces near the enemy king, treats material as secondary to attack opportunities |
| "hoards pawns obsessively" | Scores highly when White has more pawns than Black, regardless of pawn quality or position |
| "only move pawns if possible" | Note: move rule — here's the closest positional equivalent: heavily rewards pawn advancement and central pawn control, treats piece activity as secondary |
| "funniest moves" | Maximizes piece imbalance and avoids symmetrical pawn structures, preferring chaotic unbalanced positions |
