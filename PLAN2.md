# Chess Engine Hackathon — Plan 2: "Build Your Opponent"

## The Idea

The user describes a chess philosophy in plain English. Claude generates a live `evaluate()` function embodying that philosophy. The user immediately plays against their creation — and can iterate on it mid-session.

> *"An engine that hoards pawns and never trades queens"*
> → Claude writes the eval → user plays against it → *"make it even more pawn-obsessed"* → regenerated → play again

No chess.com equivalent exists because it requires LLM code generation at runtime. The generated code is shown on screen throughout. This makes the AI usage **visible, interactive, and demonstrable** to judges.

Hits all four criteria:
- **Chess quality**: Rust-powered search is fast and correct; eval is pluggable
- **AI usage**: Claude generates, the user critiques, iterates, and plays against the result in real time
- **Process**: Two clean parallel streams with clear ownership
- **Engineering**: Prompt library, eval validation/sandboxing, perft + unit tests, UCI compliance

---

## Architecture

```
chess_cubist/
├── core/                          # Rust — fast, correct, UCI-compliant
│   └── src/
│       ├── board.rs               # Board representation (shakmaty)
│       ├── search.rs              # Negamax + alpha-beta + IDDFS + quiescence
│       ├── tt.rs                  # Transposition table (Zobrist hashing)
│       ├── move_order.rs          # MVV-LVA, killer moves, history heuristic
│       └── uci.rs                 # UCI protocol interface
│
├── eval/
│   ├── base.py                    # Interface: evaluate(board: chess.Board) -> int
│   ├── classic.py                 # Materialist baseline (hand-coded, for comparison)
│   ├── generator.py               # Claude API → generates + validates eval function
│   └── generated/                 # Runtime-created evals, saved and versioned
│       └── <uuid>_<slug>.py
│
├── backend/                       # FastAPI
│   ├── main.py                    # App entrypoint, routes
│   ├── game_manager.py            # Manages active games + Rust UCI subprocess per game
│   ├── eval_generator.py          # Calls Claude, validates output, writes to eval/generated/
│   └── ws_handler.py              # WebSocket: relays moves, streams engine info lines
│
├── frontend/                      # React + TypeScript
│   └── src/
│       ├── components/
│       │   ├── PhilosophyInput.tsx  # Text box + "Generate" button + iteration history
│       │   ├── Board.tsx            # react-chessboard, drag-and-drop moves
│       │   ├── CodeViewer.tsx       # Syntax-highlighted generated eval code, live
│       │   └── EngineInfo.tsx       # Score bar, depth, principal variation
│       └── App.tsx
│
├── tests/
│   ├── test_perft.py              # Move generation node counts
│   ├── test_eval.py               # Eval sanity checks on known positions
│   ├── test_generator.py          # Claude output is valid Python, passes sandbox checks
│   └── test_search.py             # Mate-in-N correctness
│
├── prompts/
│   └── eval_generator.md          # The meta-prompt used to generate eval functions
│
└── README.md
```

---

## User Flow

1. User lands on the app — sees a chessboard and a text input
2. They type a philosophy: *"plays like a coward — avoids all exchanges, retreats pieces, never attacks"*
3. Click **Generate** → spinner → generated Python code appears in the sidebar
4. Click **Play** → choose color → game starts via WebSocket
5. User drags a piece → move sent to backend → Rust engine runs search with the generated eval → best move streamed back → board updates
6. Sidebar shows: `depth 9 | score −0.4 | pv: Nf3 e6 d4 d5...`
7. User can click **Iterate**: *"now make it willing to sacrifice pawns for open files"* → Claude regenerates → new game with updated philosophy
8. Previous versions are listed in a history panel — user can replay v1 vs v2

---

## The Claude Prompt

Documented in `prompts/eval_generator.md`. Template:

```
You are a chess engine programmer. Write a Python function:

    def evaluate(board: chess.Board) -> int

that returns a centipawn score from White's perspective (positive = White is better).

The function must embody this philosophy exactly:
{user_description}

Hard rules:
- Import only: chess, math
- No network calls, no file I/O, no side effects
- Must not raise exceptions on any legal chess.Board state
- Return an integer (centipawns)
- No explanation — return ONLY the function definition

Reference material counts (centipawns): pawn=100, knight=320, bishop=330, rook=500, queen=900
```

---

## Eval Validation Pipeline

Before any generated eval is used in a game it must pass three gates:

| Gate | What it checks | How |
|------|---------------|-----|
| Syntax | Parses as valid Python | `ast.parse()` |
| Safety | No banned imports/calls (os, subprocess, open, eval, exec) | AST node visitor |
| Sanity | Starting position ≈ 0 ±50cp; clearly winning position > 200cp | Run on 3 canonical FENs |

Failure at any gate surfaces an error in the UI with the raw Claude output — the user can refine their description and regenerate.

---

## Two Parallel Streams

### Stream A — Rust Engine Core (2 people)

Same as original plan. Deliverables:
- UCI-compliant engine via `shakmaty` + `vampirc-uci`
- Negamax + alpha-beta + quiescence + IDDFS + move ordering
- Transposition table
- Python eval callable via subprocess stdin/stdout bridge

**Target**: UCI engine that accepts an arbitrary Python eval function at startup, plays ~1200–1400 ELO from search depth alone.

### Stream B — Generator + Frontend (2 people)

- FastAPI backend: `/generate` endpoint, `/ws/game/{id}` WebSocket
- Claude eval generator with validation pipeline
- React frontend: PhilosophyInput, Board, CodeViewer, EngineInfo components
- Iteration history: list of generated evals per session, each playable

---

## Build Order / Milestones

| Milestone | Owner | When |
|-----------|-------|------|
| UCI engine plays legal chess | Stream A | Hour 3 |
| `/generate` endpoint returns valid eval | Stream B | Hour 3 |
| WebSocket game loop working end-to-end | Both | Hour 5 |
| Eval validation pipeline live | Stream B | Hour 5 |
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
| Eval sanity (3 canonical FENs) | Generated evals return sane centipawn scores |
| Generator pipeline | Claude output passes syntax + safety + sanity gates |
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
- [ ] Generator pipeline tests in `test_generator.py`
- [ ] Prompt template documented in `prompts/eval_generator.md`
- [ ] UCI compatibility verified in Arena or CuteChess
