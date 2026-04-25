# Chess Forge — AI Chess Personality Lab

Describe a chess philosophy in plain English. Claude writes a live Python evaluation function embodying that style, shown on screen as it generates. You play against your creation. After every engine move, Claude narrates what it just did in the personality's voice. When you're ready, run your engine in an automated round-robin tournament against three pre-built AI personalities and see where it ranks.

---

## Judging Criteria Coverage

| Criterion | How we address it |
|-----------|------------------|
| **Chess Engine Quality** | Rust negamax + α-β + quiescence + IDDFS + TT; UCI compliant; legal moves via shakmaty |
| **AI Usage** | Claude generates eval functions; two-model pipeline (Haiku interpret → Sonnet codegen); 5-gate validation; prompt iteration logged |
| **Process** | Parallel streams (Rust engine vs. Python/AI pipeline); agent tester; prev_plans/ shows iteration history |
| **Engineering** | 5 test modules; agent pipeline tester; UCI compliance verified; tournament results in JSON; architecture documented |

---

## Setup

**Prerequisites:** Python 3.11+, Node 18+, Rust (stable), `ANTHROPIC_API_KEY` in `.env`

```bash
make setup    # pip install -r requirements.txt && npm install
make build    # cargo build --release
make test     # pytest tests/ -v
make dev      # backend :8000 + frontend :5173
```

**Stockfish** (optional, for benchmarking):
```
Mac:   brew install stockfish
Linux: apt install stockfish
```

---

## How It Works

### 1. Describe a personality
Type any chess philosophy in plain English:
> *"A bloodthirsty attacker that sacrifices pawns to open files toward the enemy king"*

### 2. Two-step Claude pipeline
**Step 1 — Interpret (Haiku, cheap):** Restates the description as a concrete position-evaluation strategy in 1–2 sentences. Forces chess-expressible output; redirects impossible inputs like "only move pawns."

**Step 2 — Codegen (Sonnet, quality):** Generates a Python `evaluate(board: chess.Board) -> int` function. The code streams live to the UI as it generates.

### 3. Five-gate validation
Before any game starts the generated code must pass:

| Gate | Check |
|------|-------|
| Syntax | Parses as valid Python 3.9+ |
| Safety | No banned names (`os`, `subprocess`, `open`, `eval`, `exec`, `random`, `time`) |
| Sanity | Starting position ≈ 0 ±300cp; up a queen > +200cp; down a queen < −200cp |
| Determinism | Same FEN always returns same score |
| Variance | Std dev > 50cp across 10 diverse positions |

If a gate fails, the UI shows which gate failed and the exact error, prompting the user to rephrase.

### 4. Play
Drag or click pieces to move. After every engine move:
- The win probability bar updates (Lichess sigmoid formula)
- A commentary line appears, narrated in the personality's voice (Claude Sonnet)
- The eval score and search depth are displayed below the board

### 5. Tournament
Click **Run Tournament** to run a round-robin against Tal, Karpov, and Petrosian. Results display as a live bar chart and are saved to `tournament/results/` as JSON.

---

## Architecture

```
Chess Forge
├── core/                      Rust — UCI engine
│   └── src/
│       ├── uci.rs             UCI loop, EvalServer subprocess bridge, time management
│       ├── search.rs          Negamax + α-β + quiescence search + IDDFS
│       ├── move_order.rs      MVV-LVA capture ordering
│       └── tt.rs              Transposition table (32 MB, Zobrist hashing)
│
├── eval/
│   ├── eval_server.py         Persistent FEN→centipawn bridge (stdin/stdout)
│   ├── generator.py           Two-step Claude pipeline + 5-gate validation
│   ├── classic.py             Baseline: material + piece-square tables
│   └── personalities/
│       ├── tal.py             Tactical aggression, open files, king attack
│       ├── karpov.py          Outpost knights, pawn structure, bishop pair
│       └── petrosian.py       King safety, pawn shield, prophylaxis
│
├── backend/                   FastAPI
│   ├── game_manager.py        Spawns Rust + Python per game; WebSocket loop
│   ├── commentary.py          Claude: move + philosophy → narration sentence
│   ├── odds_engine.py         centipawns_to_prob() — Lichess sigmoid
│   ├── spectator_hub.py       WebSocket fan-out to N spectators
│   └── tournament_runner.py   Round-robin harness; claim_draw; 150-move cap
│
├── frontend/                  React + TypeScript (Vite)
│   └── components/
│       ├── PhilosophyInput    Interpret → generate → stream code to UI
│       ├── Board              react-chessboard; click/drag; legal move hints
│       ├── WinProbBar         Live White/Black probability bar
│       ├── EngineInfo         Depth + eval + PV display
│       ├── CommentaryFeed     Scrolling AI narration
│       ├── TournamentResults  Bar chart standings
│       └── SpectatorRoom      Share game link; viewer count
│
├── agent/                     Automated pipeline tester
│   ├── tester.py              5 sequential checks: build→eval→codegen→UCI→pipeline
│   └── results/               JSON logs of each test run
│
└── tournament/results/        JSON match logs per session
```

### Rust ↔ Python eval protocol

Rust spawns one persistent Python eval process per game. At every leaf node of the search:

```
Rust  →  Python:  <FEN string>\n
Python →  Rust:   <centipawn integer>\n    (positive = White winning)
                  ERR <message>\n          (on exception — Rust substitutes 0)
Rust  →  Python:  quit\n                  (on game end)
```

The eval_server converts the user's `evaluate(board) -> int` (White's perspective) to current-player perspective before returning to the Rust negamax, which uses the standard negation convention.

---

## AI Usage

### Model selection rationale
| Step | Model | Reason |
|------|-------|--------|
| Interpret personality | Claude Haiku | Short output; fast; low cost — runs on every keystroke submit |
| Generate `evaluate()` | Claude Sonnet | Complex code generation; needs reasoning about chess concepts |
| Per-move commentary | Claude Sonnet | Creative narration in character; quality matters for UX |

### Critical evaluation of AI output
Generated eval functions are not trusted blindly. The 5-gate validator catches:
- **Syntax errors** (Claude occasionally produces invalid Python)
- **Unsafe imports** (Claude sometimes adds `random` for "variety")
- **Wrong sign convention** (early versions returned from current-player perspective instead of White's)
- **Flat evaluations** (functions that return near-zero for all positions — std dev gate catches these)
- **Runtime crashes** (iterating over `board.king()` which returns an int, not a set)

The codegen prompt was hardened over multiple iterations to explicitly forbid each failure class discovered during testing (see Prompt Iteration section).

### Experiments run
- Personalities played against each other (see Tournament Results)
- Agent pipeline tester (`make agent`) runs build → eval → codegen → UCI → 3 live games automatically
- User-generated engines play against the three pre-built personalities in the UI tournament

---

## Testing

```bash
make test      # runs all five modules
make agent     # full pipeline smoke test (build → codegen → live games)
```

| Module | What it tests |
|--------|--------------|
| `test_perft.py` | Move generation node counts at depth 1–4 (python-chess; verifies our position parsing matches known perft values) |
| `test_eval.py` | Symmetry (flipped board = negated score), material detection, start position ≈ 0 |
| `test_generator.py` | All 5 validation gates pass/fail correctly |
| `test_search.py` | Rust engine finds best move in mate-in-one positions via UCI |
| `test_tournament.py` | Bracket math, W/D/L accounting, color alternation, JSON output |

**Agent tester** (`agent/tester.py`) chains all checks end-to-end:
1. `build_check` — Rust binary present / cargo build succeeds
2. `eval_check` — all personalities score sensibly on 3 canonical positions
3. `generator_check` — Claude API → generated function passes all 5 gates
4. `uci_check` — UCI handshake + bestmove smoke test
5. `pipeline_check` — 3 live games between personalities complete without error

Latest agent run (2026-04-25): **5/5 checks passed**.

---

## Tournament Results

Run `make tournament` to populate with fresh data. Results are saved to `tournament/results/`.

### Personality round-robin (2 games per pair, 200ms/move)

Results from `tournament/results/f25255c6.json` — includes a user-generated "Coward" engine (retreats all pieces, avoids exchanges):

| Engine | W | D | L | Points |
|--------|---|---|---|--------|
| Petrosian | 6 | 0 | 0 | 12 |
| Karpov | 3 | 1 | 2 | 7 |
| Tal | 2 | 1 | 3 | 5 |
| Coward (user) | 0 | 0 | 6 | 0 |

Notable: Petrosian's prophylactic style (king safety + pawn shield) dominated at short time controls. The user's Coward engine — deliberately over-penalizing aggression — lost every game as expected, confirming the personality system produces meaningfully different play styles.

---

## UCI Compatibility

The Rust engine (`core/target/release/chess_forge`) is UCI-compliant:

```
→ uci
← id name ChessForge
← id author Chess Cubist
← uciok
→ isready
← readyok
→ position startpos moves e2e4 e7e5
→ go movetime 500 depth 4
← info depth 1 score cp 15 pv g1f3
← info depth 2 score cp 10 pv g1f3 b8c6
← info depth 3 score cp 20 pv g1f3 b8c6 f1c4
← info depth 4 score cp 15 pv g1f3 b8c6 f1c4 g8f6
← bestmove g1f3
```

Compatible with CuteChess, Arena, and any standard UCI GUI.

---

## Prompt Iteration Notes

The two-step Claude pipeline went through several iterations before producing reliable output.

### Interpretation prompt

**v1:** `Restate "{description}" as a chess evaluation strategy in one sentence.`
Problem: vague output; "only move pawns" produced an architecturally impossible strategy.

**v2 (final):** Forces output as `"score this board state highly when [X]"`. Explicitly redirects move-rule inputs to the nearest positional equivalent and prefixes the response with a warning so the user understands the translation.

### Codegen prompt

**v1:** Asked for any Python function that "plays like X."
Problems discovered in testing:
- Used `random` for "chaotic" personalities → non-deterministic
- Returned `float` instead of `int` → type errors downstream
- Called `board.push()` inside the function → corrupted board state
- Iterated over `board.king(color)` → `int` is not iterable, raised `TypeError`
- Used `board.piece_map()` → includes kings, caused `KeyError: 6`
- Added large personality bonuses of 5–20cp → drowned out by material, personality invisible

**v2 (final):** Hard rules added to prompt:
- Import only `chess`, `math`
- No `board.push()` / `board.pop()` — board is read-only
- No `board.piece_map()` — use `board.pieces(piece_type, color)` explicitly
- `board.king()` returns a single int — never iterate over it
- Return type must be `int`
- Deterministic — same board always returns same score
- Personality bonuses must be 50–150cp to compete with material

Each failure class was discovered by running generated functions against the 5-gate validator and against real games, then hardened into the prompt.

---

## Process

The project was built in two parallel streams:

**Stream A — Rust engine:** UCI loop, search (negamax + α-β + quiescence + IDDFS), transposition table, move ordering. Tested via `test_search.py` and UCI smoke tests.

**Stream B — Python/AI pipeline:** eval generator, personality eval functions, commentary, tournament runner, FastAPI backend, React frontend. Tested via `test_eval.py`, `test_generator.py`, `test_tournament.py`, and the agent tester.

Integration point: the `--eval-server` flag on the Rust binary, which spawns a Python eval process and communicates via stdin/stdout FEN strings. Streams never blocked each other.

Planning history is preserved in `prev_plans/` — five plan revisions show how scope was refined from initial concept to final architecture.

---

## API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/interpret` | POST | Personality description → chess strategy (Haiku) |
| `/api/generate` | POST | Strategy → validated `evaluate()` function (Sonnet) |
| `/api/game/start` | POST | Reserve a game ID; returns `game_id` |
| `/ws/game/{id}` | WS | Player move loop: send UCI move, receive FEN + eval + commentary |
| `/ws/spectate/{id}` | WS | Read-only game stream for spectators |
| `/api/tournament` | POST | Run round-robin; returns standings + matchup log |
| `/health` | GET | Liveness check |

---

## Environment Variables

Create a root `.env` file before running `make dev`:

```bash
ANTHROPIC_API_KEY=your_api_key_here
```

The app reads this key for interpretation, code generation, and commentary calls. The `.env` file is ignored by git.

---

## Common Commands

| Command | Purpose |
|---------|---------|
| `make setup` | Install Python and frontend dependencies |
| `make build` | Build the Rust UCI engine in release mode |
| `make test` | Run the pytest suite |
| `make agent` | Run the full pipeline smoke tester |
| `make tournament` | Run a 10-game-per-pair personality round-robin |
| `make bench` | Benchmark against Stockfish skill level 5 |
| `make dev` | Start FastAPI on `:8000` and Vite on `:5173` |

During development, open the frontend at:

```text
http://localhost:5173
```

The backend API runs at:

```text
http://localhost:8000
```

---

## Demo Script

Use this flow for a live judging demo:

1. Start the app with `make dev`.
2. Enter a personality such as:

   > A reckless attacker that sacrifices pawns to open files toward the enemy king.

3. Show the interpreted chess strategy.
4. Generate the eval and point out the live code viewer.
5. Show that the validator accepted the generated function.
6. Play several moves against the generated engine.
7. Call attention to:
   - engine eval and depth
   - win probability bar
   - personality-specific commentary
8. Run the UI tournament against Tal, Karpov, and Petrosian.
9. Show the final standings and the saved JSON result.
10. Mention that the same system can be run headlessly with `make tournament` and tested with `make agent`.

The shortest judge-facing pitch:

> Chess Forge turns natural language into a real chess engine personality. Claude writes the evaluation function, our validator checks it, the Rust engine searches with it, and the tournament harness measures whether the personality actually changes play.

---

## Current Status

Implemented:

- Rust UCI engine with search, move ordering, transposition table, and Python eval bridge.
- Python eval server using line-oriented FEN-to-centipawn protocol.
- Claude-powered interpretation and code generation pipeline.
- Five-gate generated-code validation.
- Built-in Tal, Karpov, Petrosian, and Classic personalities.
- FastAPI game, generation, spectator, and tournament endpoints.
- React frontend with board, code viewer, engine info, commentary, win probability, and tournament display.
- Automated tests and agent pipeline checker.

Known limitations:

- Generated eval functions are intentionally restricted to board evaluation only; they cannot directly force move rules like "always move the queen."
- Python eval calls are slower than native Rust eval, so very deep search is not the goal for generated personalities.
- Commentary depends on Claude API availability.
- Stockfish benchmarking requires a local `stockfish` binary.
- Betting/market mechanics are currently represented as win probability and spectator UX primitives, not real-money trading.

---

## Design Decisions

### Why generate eval functions instead of full engines?

Full engine generation is too risky for a hackathon: move legality, time management, UCI behavior, and search bugs would all vary across generated outputs. Keeping Rust responsible for search and legality gives the project a stable chess core, while Claude controls the style through evaluation.

### Why use a Python eval server?

The generated code is Python because `python-chess` gives Claude a clear, high-level board API. Rust keeps one persistent Python process alive per game, avoiding subprocess startup cost on every evaluation.

### Why fake markets instead of real betting?

Real Kalshi or Polymarket integration introduces compliance, identity, jurisdiction, and real-money risk. For the hackathon, fake chips and live odds preserve the interactive prediction-market idea while keeping the project focused on engine behavior and experimentation.

---

## Roadmap

High-value next steps:

- Add a richer spectator room with fake-chip markets for winner, move count, and sacrifice-before-move-20.
- Cache generated eval results and prompt metadata for replayable experiments.
- Add Stockfish benchmark summaries to the frontend.
- Add export support for generated personalities as standalone UCI configs.
- Add more tactical test positions for mate, material wins, and defensive resources.
- Add a report generator that turns tournament JSON into a judge-ready experiment summary.

Stretch goals:

- Lichess bot deployment for selected personalities.
- Shareable spectator links.
- Persistent leaderboard for generated engines.
- More personality archetypes and automatic prompt mutation based on tournament losses.

---

## Repository Notes

- `docs/` contains supporting hackathon documentation: feature guide, testing notes, final structure, and planning summary.
- `assets/presentation/` contains presentation images and diagrams used by `PRESENTATION.md`.
- `analysis/` contains the quality-metrics notebook used to generate presentation charts.
- `tools/` contains one-off helper scripts, including the blueprint image generator.
- `prev_plans/` preserves earlier planning iterations and the final synthesis.
- `agent/results/` stores automated pipeline run logs.
- `tournament/results/` stores self-play tournament JSON.
- `eval/generated/` is intentionally gitignored because it contains runtime-created eval files.
- `core/target/`, `frontend/node_modules/`, and `frontend/dist/` are build artifacts and are not committed.

---

## Acknowledgements

Built around standard chess-engine ideas: UCI protocol support, alpha-beta search, quiescence search, transposition tables, move ordering, self-play evaluation, and Stockfish benchmarking. The differentiator is the Claude-driven evaluation pipeline: users shape the engine's chess philosophy directly, then the system tests that philosophy through actual games.
