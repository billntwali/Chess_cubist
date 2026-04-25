# Chess Forge Feature Guide

This document explains the major features in Chess Forge, the AI workflows behind them, and the chess protocols and engineering foundations the project builds upon. It is written for hackathon presentation and maps directly to the criteria in `CLAUDE.md`.

## One-Sentence Pitch

Chess Forge lets a user describe any chess personality in plain English, generates a real evaluation function for that personality, runs it inside a UCI-compatible Rust chess engine, narrates its moves, and benchmarks it in tournaments against other AI-generated styles.

## Hackathon Criteria Map

| Criterion | Where It Shows Up |
|-----------|-------------------|
| **Chess Engine Quality** | Rust engine, legal move generation, alpha-beta search, quiescence, transposition table, UCI support |
| **AI Usage** | Claude interprets personalities, generates eval code, helps narrate moves, and is critically evaluated through validation/tests |
| **Process and Parallelization** | Rust core, Python eval pipeline, backend orchestration, frontend UI, and tournament tooling are cleanly separated |
| **Engineering Quality** | Unit tests, perft tests, tournament tests, generated-code validation, prompt iteration docs, UCI compatibility, JSON result logs |

---

## Feature 1: Natural-Language Chess Personality Builder

### What It Does

The user types a prompt such as:

```text
play like magnus carlsen
```

or:

```text
play like a reckless attacker
```

Chess Forge turns that plain-English style into a chess engine personality.

### Why It Matters

Most chess apps let users choose preset bots. Chess Forge lets users invent the bot's actual evaluation logic. The generated personality is not just a label or avatar; it changes how the engine scores positions.

### AI Workflow

1. **Interpretation call**
   - Model: Claude Haiku
   - Input: user description
   - Output: chess-expressible strategy description
   - Example: "Magnus" becomes a style that rewards small positional advantages, centralized pieces, durable pawn structures, and conversion pressure.

2. **Code generation call**
   - Model: Claude Sonnet
   - Input: interpreted strategy
   - Output: Python function:

```python
def evaluate(board: chess.Board) -> int:
    ...
```

3. **Fallback path**
   - If Claude times out, returns malformed code, or produces truncated output, the system generates a local prompt-aware fallback eval.
   - This prevents malformed Python from reaching the user.

### Engineering Criteria

- Demonstrates creative AI usage.
- Shows critical evaluation of AI-generated code.
- Uses fallback logic for reliability and cost/latency control.

---

## Feature 2: Generated Evaluation Functions

### What It Does

Every personality becomes a Python `evaluate(board)` function. The function returns a centipawn score from White's perspective:

- Positive score: White is better.
- Negative score: Black is better.
- Around zero: balanced.

### Why It Matters

The evaluation function is the "taste" of a chess engine. Search finds moves, but evaluation decides what kinds of positions the engine wants.

Different generated evals can reward different chess ideas:

- Material
- King safety
- Piece activity
- Pawn structure
- Open files
- Outposts
- Passed pawns
- Space advantage
- Attacking chances
- Defensive compactness

### AI Workflow

Claude writes the eval function, but the app does not trust it blindly. The generated code must pass validation before it can be used in a game.

### Engineering Criteria

- AI-generated code is treated as untrusted input.
- The generated code becomes part of a real chess-playing loop.
- Each generated personality can be tested empirically in games.

---

## Feature 3: Five-Gate Validation Pipeline

### What It Does

Before a generated eval can run inside the engine, it must pass five validation gates.

| Gate | What It Checks |
|------|----------------|
| **Syntax** | Code parses as valid Python |
| **Safety** | No banned names or unsafe imports such as `os`, `subprocess`, `open`, `eval`, `exec`, `random`, or `time` |
| **Sanity** | Starting position is roughly equal; queen-up positions score correctly |
| **Determinism** | Same board returns the same score every time |
| **Variance** | Scores vary across different positions, proving the eval is not constant |

### Why It Matters

This is the main safety layer between Claude-generated code and the engine. It catches the kinds of mistakes LLMs commonly make:

- Invalid indentation
- Unsafe imports
- Non-deterministic behavior
- Wrong sign convention
- Constant evaluations
- Runtime crashes on legal boards

### Example Failure Fixed During Testing

The prompt:

```text
play like magnus carlsen
```

once produced malformed Python:

```text
Syntax error: expected an indented block (<unknown>, line 313)
```

The generator was hardened so this class of failure now falls back to valid code instead of reaching the UI.

### Engineering Criteria

- Directly supports rigor and engineering quality.
- Shows that AI-generated code is tested, not blindly accepted.
- Provides evidence of prompt iteration and failure analysis.

---

## Feature 4: Rust Chess Engine Core

### What It Does

The Rust engine handles the actual chess search and move choice.

Core engine features:

- Legal move handling through `shakmaty`
- Negamax search
- Alpha-beta pruning
- Iterative deepening
- Quiescence search
- Move ordering
- Transposition table
- Built-in fallback material evaluation

### Why It Matters

Claude controls the personality, but Rust controls legality and search discipline. This keeps the project from becoming a fragile generated-code demo.

The engine still plays legal chess even if the AI-generated eval fails, because the Rust side can fall back to a built-in material eval.

### Engineering Criteria

- Shows real chess-engine implementation.
- Uses established chess-engine techniques.
- Separates chess correctness from AI personality generation.

---

## Feature 5: Universal Chess Interface (UCI) Support

### What It Does

The Rust engine speaks UCI, the standard protocol used by chess engines and GUIs.

Example UCI interaction:

```text
uci
id name ChessForge
id author Chess Cubist
uciok
isready
readyok
position startpos moves e2e4 e7e5
go movetime 500 depth 4
bestmove g1f3
```

### Why It Matters

UCI compatibility means the engine is not locked to the web app. It can be tested or loaded through standard chess tooling such as CuteChess, Arena, or other UCI-compatible interfaces.

### Existing Protocol Built Upon

- **UCI**: standard chess engine protocol.
- **UCI moves**: coordinate notation such as `e2e4`.
- **Centipawn scores**: common chess-engine scoring unit.

### Engineering Criteria

- Demonstrates prior-art research.
- Makes the engine interoperable.
- Supports independent testing outside the frontend.

---

## Feature 6: Rust-to-Python Eval Server Protocol

### What It Does

Rust performs search, but Python evaluates generated personalities. The bridge is a persistent stdin/stdout protocol.

Protocol:

```text
Rust  -> Python: <FEN string>\n
Python -> Rust:  <centipawn integer>\n
Rust  -> Python: quit\n
```

On error:

```text
Python -> Rust: ERR <message>\n
```

If Rust receives an error, it substitutes a safe score and continues.

### Why It Matters

This lets the team combine:

- Rust speed and reliability for search.
- Python flexibility for generated eval functions.
- `python-chess` convenience for board queries.

The Python process persists for the entire game, so the app does not spawn a new process for every evaluation call.

### Existing Protocols and Formats Built Upon

- **FEN**: Forsyth-Edwards Notation, used to serialize board state.
- **stdin/stdout line protocol**: simple process communication.
- **Centipawn scores**: standard engine evaluation format.
- **python-chess**: trusted board API for generated eval code.

### Engineering Criteria

- Clear integration contract between independent workstreams.
- Allows Rust and Python teams to build in parallel.
- Easy to test in isolation.

---

## Feature 7: Interactive Web App

### What It Does

The frontend provides the live user experience:

- Philosophy input
- Code viewer for generated evals
- Chessboard
- Engine score display
- Principal variation display
- Win probability bar
- Commentary feed
- Tournament result chart

### Why It Matters

The app makes the AI workflow visible. Users can see not just the move, but the generated code and tournament behavior behind the move.

### Engineering Stack

- React
- TypeScript
- Vite
- `react-chessboard`
- `chess.js`

### Engineering Criteria

- Makes the demo understandable.
- Turns technical engine behavior into an interactive product.
- Helps judges see AI generation, validation, play, and benchmarking in one flow.

---

## Feature 8: FastAPI Backend Orchestration

### What It Does

The backend coordinates the system:

- Calls Claude for interpretation.
- Calls Claude for code generation.
- Validates generated evals.
- Saves generated eval files.
- Starts games.
- Spawns engine processes.
- Handles player WebSocket moves.
- Runs tournaments.
- Broadcasts spectator updates.

### Main Endpoints

| Endpoint | Purpose |
|----------|---------|
| `POST /api/interpret` | Convert personality prompt into chess strategy |
| `POST /api/generate` | Generate and validate eval function |
| `POST /api/game/start` | Reserve a game ID |
| `WS /ws/game/{id}` | Player move loop |
| `WS /ws/spectate/{id}` | Read-only spectator stream |
| `POST /api/tournament` | Run a round-robin tournament |
| `GET /health` | Health check |

### Protocols Built Upon

- HTTP JSON APIs
- WebSockets
- UCI subprocess communication
- FEN board serialization

### Engineering Criteria

- Clean orchestration layer.
- Decouples frontend from engine internals.
- Enables parallel development across frontend, backend, engine, and AI pipeline.

---

## Feature 9: Claude Move Commentary

### What It Does

After the engine makes a move, Claude writes a short narration in the personality's voice.

Example:

```text
The Coward tucks the bishop back, unwilling to risk a single exchange.
```

### Why It Matters

The generated eval affects the move. The commentary explains the move in a way humans can understand and makes the personality feel alive.

### AI Workflow

Input to commentary:

- Personality description
- Engine move
- Current FEN
- Engine evaluation

Output:

- One concise sentence of narration.

### Engineering Criteria

- Demonstrates AI used beyond code generation.
- Improves explainability and demo clarity.
- Keeps commentary separate from move legality and engine search.

---

## Feature 10: Win Probability Bar

### What It Does

The app converts centipawn evaluations into a White win probability estimate.

Conceptually:

```text
centipawns -> probability
```

This powers the live probability bar in the UI.

### Why It Matters

Centipawn scores are engine-native but not user-friendly. A win probability bar makes engine evaluation legible to spectators and beginners.

### Existing Ideas Built Upon

- Centipawn scoring from chess engines.
- Sigmoid-style conversion similar to common chess-analysis interfaces.

### Engineering Criteria

- Makes technical evaluation output understandable.
- Supports spectator and tournament storytelling.

---

## Feature 11: Round-Robin Tournament Runner

### What It Does

The tournament runner pits multiple personalities against each other:

- User-generated eval
- Tal-style eval
- Karpov-style eval
- Petrosian-style eval
- Classic baseline eval

It alternates colors, records wins/draws/losses, and saves JSON logs.

### Why It Matters

This turns "the AI wrote a different function" into an experiment:

- Does the personality play differently?
- Does it win or lose?
- Does a defensive eval beat an attacking eval?
- Does a user-generated eval survive against baselines?

### Output Format

Tournament results include:

- Session ID
- Timestamp
- Standings
- Matchup log
- Game result for each pairing

### Engineering Criteria

- Strong evidence of rigor.
- Enables self-play benchmarking.
- Demonstrates process and experimentation with AI-generated engines.

---

## Feature 12: Prebuilt Personalities

### What It Does

The app includes baseline personalities:

| Personality | Style |
|-------------|-------|
| **Classic** | Material and piece-square-table baseline |
| **Tal** | Tactical aggression, open files, king attack |
| **Karpov** | Positional pressure, outposts, structure |
| **Petrosian** | King safety, prophylaxis, defensive solidity |

### Why It Matters

Prebuilt personalities provide stable opponents for user-generated engines. They also make tournaments easy to run during the demo.

### AI Workflow

These personalities were created or refined through Claude-assisted eval generation and prompt iteration.

### Engineering Criteria

- Enables controlled comparison.
- Makes the demo reliable even if live generation is slow.
- Supports self-play experiments.

---

## Feature 13: Automated Test Suite

### What It Does

The test suite checks the most important parts of the system.

| Test Module | Purpose |
|-------------|---------|
| `test_perft.py` | Validates move generation against known node counts |
| `test_eval.py` | Checks eval symmetry, material detection, and sane scores |
| `test_generator.py` | Tests generated-code validation and fallback behavior |
| `test_search.py` | Checks UCI/search behavior on tactical positions |
| `test_tournament.py` | Checks tournament bracket math, W/D/L accounting, and JSON output |

### Why It Matters

Chess engines fail in subtle ways. Testing catches errors in legality, evaluation sign conventions, generated-code safety, and tournament accounting.

### Engineering Criteria

- Directly supports rigor.
- Provides evidence of correctness.
- Documents how AI-generated code is evaluated.

---

## Feature 14: Agent Pipeline Tester

### What It Does

The agent tester runs multiple checks end to end:

1. Build check
2. Eval check
3. Generator check
4. UCI check
5. Pipeline check

### Why It Matters

The pipeline tester proves the pieces work together, not just individually.

### Engineering Criteria

- Integration testing.
- Reproducible validation.
- Useful for hackathon demo confidence.

---

## Feature 15: Stockfish Benchmark Hook

### What It Does

The repo includes a benchmark path for testing against Stockfish when installed locally.

Command:

```bash
make bench
```

### Why It Matters

Stockfish is the reference chess engine. Even if Chess Forge is not trying to beat Stockfish, benchmarking against it gives a known external standard.

### Existing Protocol Built Upon

- Stockfish UCI engine.
- UCI skill levels.
- Standard engine-vs-engine testing.

### Engineering Criteria

- Demonstrates prior-art awareness.
- Provides external calibration.
- Supports quantitative evaluation.

---

## End-to-End Demo Flow

Use this during judging:

1. Run the app.

```bash
make dev
```

2. Enter a prompt.

```text
play like magnus carlsen
```

3. Show interpretation.
4. Generate the eval.
5. Show the code viewer.
6. Explain the five validation gates.
7. Play a few moves against the generated engine.
8. Point out:
   - board state
   - engine eval
   - principal variation
   - win probability
   - commentary
9. Run the tournament.
10. Show standings and explain that this is self-play benchmarking.

---

## Architecture at a Glance

```text
User prompt
   |
   v
Claude Haiku interpretation
   |
   v
Claude Sonnet code generation
   |
   v
Five-gate validator
   |
   v
Saved Python evaluate(board) function
   |
   v
Rust UCI engine search
   |
   v
Python eval server over FEN stdin/stdout
   |
   v
Best move + eval + PV
   |
   v
FastAPI WebSocket
   |
   v
React UI + commentary + tournament results
```

---

## Why This Is Hackathon-Worthy

Chess Forge is not just a chess bot. It is a system for creating, testing, and comparing chess personalities.

It combines:

- A real Rust chess engine
- Standard chess protocols
- Claude-generated evaluation code
- Generated-code validation
- Interactive web play
- Move narration
- Self-play tournaments
- Testing and benchmark infrastructure

The central idea is that the user does not merely choose an opponent. The user describes an opponent, Claude writes the opponent's chess brain, and the engine proves that brain through actual games.

That directly addresses the hackathon criteria:

- **Creativity**: natural-language engine creation
- **Rigor**: validation gates, tests, tournaments, benchmarks
- **Ingenuity**: Rust search plus Python generated eval bridge
- **Engineering**: UCI, FastAPI, WebSockets, JSON logs, modular architecture

