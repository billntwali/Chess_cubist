# Chess Engine Hackathon — Plan 4: "Build Your Opponent"

Builds on LLM-PLAN3. Changes from Plan 3:
- Interpretation prompt updated to redirect move-priority philosophies to positional equivalents
- No `filter_moves` support — the system only generates `evaluate()` functions; move-priority inputs are redirected at the interpretation step rather than handled architecturally

---

## The Idea

The user describes a chess philosophy in plain English. Claude generates a live `evaluate()` function embodying that philosophy. The user immediately plays against their creation — and can iterate on it mid-session.

> *"An engine that hoards pawns and never trades queens"*
> → Claude writes the eval → user plays against it → *"make it even more pawn-obsessed"* → regenerated → play again

No chess.com equivalent exists because it requires LLM code generation at runtime. The generated code is shown on screen throughout. This makes the AI usage **visible, interactive, and demonstrable** to judges.

---

## Architecture

```
chess_cubist/
├── core/                          # Rust — UCI-compliant search engine
│   └── src/
│       ├── board.rs               # Board representation (shakmaty)
│       ├── search.rs              # Negamax + alpha-beta + IDDFS + quiescence
│       ├── tt.rs                  # Transposition table (Zobrist hashing)
│       ├── move_order.rs          # MVV-LVA, killer moves, history heuristic
│       └── uci.rs                 # UCI protocol interface
│
├── eval/
│   ├── eval_server.py             # Persistent eval process — Rust talks to this
│   ├── classic.py                 # Materialist baseline (hand-coded, for comparison)
│   ├── generator.py               # Claude API → generates + validates eval function
│   └── generated/                 # Runtime-created evals, saved and versioned
│       └── <uuid>_<slug>.py
│
├── backend/                       # FastAPI
│   ├── main.py
│   ├── game_manager.py            # Spawns Rust + Python processes per game
│   ├── eval_generator.py          # Calls Claude, validates output, writes to eval/generated/
│   └── ws_handler.py              # WebSocket: relays moves, streams engine info lines
│
├── frontend/                      # React + TypeScript
│   └── src/
│       ├── components/
│       │   ├── PhilosophyInput.tsx
│       │   ├── Board.tsx
│       │   ├── CodeViewer.tsx
│       │   └── EngineInfo.tsx
│       └── App.tsx
│
├── tests/
│   ├── test_perft.py
│   ├── test_eval.py
│   ├── test_generator.py
│   └── test_search.py
│
├── prompts/
│   └── eval_generator.md
│
└── README.md
```

---

## Rust-Python Interface Contract

This is the integration point between Stream A and Stream B. Both streams must implement their side exactly as specified here.

### Overview

Rust spawns one persistent Python process at game start. For each leaf-node evaluation during search, Rust writes a FEN string to the process's stdin and reads back a centipawn integer from stdout. When the game ends, Rust sends `quit`.

Seconds-per-move latency is acceptable — the bridge is stdin/stdout with no subprocess-per-call overhead.

### The eval server (`eval/eval_server.py`)

Stream B owns and implements this file.

```python
import sys
import chess
import importlib.util

def load_eval(path: str):
    spec = importlib.util.spec_from_file_location("eval_fn", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.evaluate

if __name__ == "__main__":
    evaluate = load_eval(sys.argv[1])
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        if line == "quit":
            break
        try:
            board = chess.Board(line)
            score = int(evaluate(board))
            print(score, flush=True)
        except Exception as e:
            print(f"ERR {e}", flush=True)
```

Invocation: `python eval_server.py path/to/generated_eval.py`

### Protocol (line-oriented, UTF-8)

| Direction | Message | Example |
|-----------|---------|---------|
| Rust → Python | FEN string + `\n` | `rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1\n` |
| Python → Rust | Integer score + `\n` | `35\n` |
| Rust → Python | `quit\n` | terminates the Python process |
| Python → Rust (error) | `ERR <message>\n` | `ERR invalid fen\n` |

Rules:
- One FEN per line, one score per line — strictly alternating
- Score is from White's perspective (positive = White better), in centipawns
- Rust must flush after writing each FEN
- Python must flush after writing each score (`flush=True`)
- If Rust receives a line starting with `ERR`, it uses `0` as the score and logs the error
- If the Python process exits unexpectedly, Rust falls back to its built-in material eval

### Rust side (Stream A responsibility)

In `search.rs`, the leaf-node eval call:

```rust
fn query_python_eval(stdin: &mut ChildStdin, stdout: &mut BufReader<ChildStdout>, fen: &str) -> i32 {
    writeln!(stdin, "{}", fen).unwrap();
    stdin.flush().unwrap();
    let mut line = String::new();
    stdout.read_line(&mut line).unwrap();
    let line = line.trim();
    if line.starts_with("ERR") {
        return 0;
    }
    line.parse::<i32>().unwrap_or(0)
}
```

The `ChildStdin` and `ChildStdout` handles are stored in a game state struct and reused for the entire game.

### Startup sequence

1. Backend (`game_manager.py`) receives a new game request with `eval_path`
2. Backend spawns the Rust binary: `./core/target/release/chess_engine --eval-server "python eval/eval_server.py <eval_path>"`
3. Rust starts the Python process internally on startup using `--eval-server` argument
4. Rust signals ready via UCI `uciok` / `readyok` handshake
5. Backend connects via UCI over Rust's stdin/stdout

### Testing the interface in isolation

Before integrating, Stream B should verify `eval_server.py` manually:

```bash
echo "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1" | python eval/eval_server.py eval/classic.py
# expected: a small integer near 0
```

Stream A should verify the Rust caller with a mock Python script that echoes `42` for any input.

---

## User Flow

1. User lands on the app — sees a chessboard and a text input
2. They type a philosophy: *"plays like a coward — avoids all exchanges, retreats pieces, never attacks"*
3. Click **Generate** → Claude interprets input as the nearest chess concept and shows it: *"Interpreted as: maximize king safety and pawn structure integrity, penalize open files near own king, avoid piece trades"* — user can adjust before proceeding
4. Spinner → generated Python code appears in the sidebar
5. Code passes the validation pipeline; if any gate fails, the UI shows which gate failed and suggests a rephrasing
6. Click **Play** → choose color → game starts via WebSocket
7. User drags a piece → move sent to backend → Rust engine runs search using the Python eval server → best move streamed back → board updates
8. Sidebar shows: `depth 9 | score −0.4 | pv: Nf3 e6 d4 d5...`
9. User can click **Iterate**: *"now make it willing to sacrifice pawns for open files"* → Claude regenerates → new game starts with updated philosophy
10. Previous versions are listed in a history panel — clicking one **starts a new game** with that eval (not a replay of old moves)

---

## The Claude Prompts

**Step 1 — Interpretation prompt** (shown to user before codegen):
```
The user wants a chess engine with this philosophy: "{user_description}"

Your job is to restate this as a concrete chess POSITION evaluation strategy
in one sentence — something that can be expressed as: "score this board state
highly when [X]."

Use only chess concepts: piece activity, king safety, pawn structure, material
balance, mobility, open files, outposts, etc.

Two categories of input require special handling:

1. Non-chess concepts (e.g. "funniest moves", "most chaotic", "most dramatic"):
   Map to the nearest meaningful chess analogue.
   Example: "funniest" → "maximizes piece imbalance and avoids symmetrical pawn structures"

2. Move-priority rules (e.g. "only move pawns", "always move the knight first",
   "never move the queen"): These cannot be expressed as position evaluations.
   Instead, redirect to the closest positional philosophy.
   Example: "only move pawns if possible" → "heavily rewards pawn advancement
   and central pawn control, treats piece activity as secondary"
   Prefix the restatement with: "Note: your description was a move rule, which
   can't be directly implemented — here's the closest positional equivalent:"

Return ONLY the one-sentence restatement (plus the Note prefix if applicable).
No further explanation.
```

**Step 2 — Codegen prompt** (runs after user confirms interpretation):
```
You are a chess engine programmer. Write a Python function:

    def evaluate(board: chess.Board) -> int

that returns a centipawn score from White's perspective (positive = White is better).

The function must embody this philosophy exactly:
{interpreted_description}

Hard rules:
- Import only: chess, math
- No random, no time, no network calls, no file I/O, no side effects
- Must not raise exceptions on any legal chess.Board state
- Must be deterministic — same board must always return the same score
- Return an integer (centipawns)
- No explanation — return ONLY the function definition

Reference material counts (centipawns): pawn=100, knight=320, bishop=330, rook=500, queen=900
```

---

## Eval Validation Pipeline

| Gate | What it checks | How |
|------|---------------|-----|
| Syntax | Parses as valid Python | `ast.parse()` |
| Safety | No banned names: `os`, `subprocess`, `open`, `eval`, `exec`, `random`, `time`, `__import__`, `getattr` on builtins | AST node visitor |
| Sanity | Starting position ≈ 0 ±50cp; white up a queen > 200cp; black up a queen < -200cp | 3 canonical FENs |
| Determinism | Same FEN evaluated twice returns identical score | `eval(pos) == eval(pos)` on 3 positions |
| Variance | Std dev across 10 diverse positions > 50cp | Catches constants and near-constant evals |

Failure at any gate surfaces: which gate failed, the raw Claude output, and a suggested rephrasing.

---

## Two Parallel Streams

### Stream A — Rust Engine Core

Deliverables:
- UCI-compliant engine via `shakmaty` + `vampirc-uci`
- Negamax + alpha-beta + quiescence + IDDFS + move ordering
- Transposition table
- `--eval-server <cmd>` flag: spawns the given command as a subprocess, uses the stdin/stdout protocol above for leaf-node evaluation
- Fallback to built-in material eval if Python process is unavailable or returns ERR

### Stream B — Generator + Frontend

Deliverables:
- `eval/eval_server.py` — the persistent eval process (see Interface Contract)
- `eval/generator.py` — Claude API call, two-step prompt, validation pipeline
- FastAPI: `/generate` endpoint, `/ws/game/{id}` WebSocket
- React frontend: PhilosophyInput, Board, CodeViewer, EngineInfo, iteration history panel
- Iteration history: clicking a past version starts a new game with that eval file

**Interface dependency**: Stream B must have `eval_server.py` testable standalone (see testing steps above) before the integration milestone.

---

## Build Order / Milestones

| Milestone | Owner | When |
|-----------|-------|------|
| UCI engine plays legal chess (built-in eval) | Stream A | Hour 3 |
| `eval_server.py` testable standalone | Stream B | Hour 3 |
| `/generate` endpoint returns validated eval | Stream B | Hour 4 |
| Rust `--eval-server` flag works with mock Python | Stream A | Hour 4 |
| **Integration: Rust + Python eval server end-to-end** | Both | Hour 5 |
| WebSocket game loop working in browser | Both | Hour 6 |
| Quiescence + move ordering done | Stream A | Hour 6 |
| CodeViewer + iteration history in UI | Stream B | Hour 7 |
| Transposition table integrated | Stream A | Hour 8 |
| Perft + unit + generator tests passing | Both | Day 2 morning |
| README + prompt docs written | Both | Day 2 afternoon |

---

## Testing Strategy

| Test | Purpose |
|------|---------|
| Perft depth 4 | Validates move generation correctness |
| Mate-in-N (20 puzzles) | Verifies search finds forced mates |
| `eval_server.py` standalone | FEN in → integer out, ERR on bad input |
| Eval sanity (3 canonical FENs) | Generated evals return sane centipawn scores |
| Eval determinism | Same position always returns same score |
| Eval variance (10 diverse FENs) | Eval is position-sensitive, not constant |
| Generator pipeline | Claude output passes all five validation gates |
| Baseline comparison | Generated eval vs. classic.py in 10-game self-play |

---

## Stretch Goals

- **Personality clash**: pit two user-generated evals against each other in an automated tournament; show results in the UI
- **"Why did it play that?"**: after each engine move, call Claude to explain the move in the context of the stated philosophy
- **Export your engine**: download the generated eval + Rust binary as a standalone UCI engine
- **lichess-bot**: deploy a user's generated personality as a live lichess bot

---

## Engineering Quality Checklist

- [ ] README: setup, architecture, how the generator works, example philosophies
- [ ] Docstrings on all public Python functions and Rust `pub fn`s
- [ ] `Cargo.toml`, `requirements.txt` / `pyproject.toml`
- [ ] Perft tests passing at depth 4
- [ ] Mate-in-N tests passing
- [ ] `eval_server.py` tested standalone
- [ ] Generator pipeline tests in `test_generator.py`
- [ ] Prompt template documented in `prompts/eval_generator.md`
- [ ] UCI compatibility verified in Arena or CuteChess
