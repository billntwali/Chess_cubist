# Chess Forge — AI Chess Personality Lab

You describe a chess personality in plain English. Claude writes a live Python evaluation function embodying that philosophy, shown on screen the entire time. You play against your creation. After every engine move, Claude narrates what it just did in the personality's voice. When you're satisfied, run your creation in an automated tournament against three classic AI personalities and see where it ranks.

---

## Setup

**Prerequisites:** Python 3.11+, Node 18+, Rust (stable)

```bash
# 1. Install all dependencies
make setup

# 2. Compile the Rust engine
make build

# 3. Verify everything works
make test
```

**Stockfish** (for benchmarking only):
```
Mac:   brew install stockfish
Linux: apt install stockfish
```

---

## Running the App

```bash
make dev
```

- Backend: http://localhost:8000
- Frontend: http://localhost:5173

---

## How It Works

### 1. Describe a personality
Type any chess philosophy in plain English:
> *"A bloodthirsty attacker that sacrifices pawns to open files toward the enemy king"*

Claude first restates it as a concrete evaluation strategy, then generates a Python `evaluate(board) -> int` function. The code appears live in the UI.

### 2. Validation (5 gates)
Before any game starts, the generated code must pass:

| Gate | Check |
|------|-------|
| Syntax | Parses as valid Python |
| Safety | No banned names (`os`, `subprocess`, `open`, `eval`, `exec`, `random`, `time`, `__import__`) |
| Sanity | Starting position ≈ 0 ±50cp; up a queen > 200cp |
| Determinism | Same FEN always returns same score |
| Variance | Std dev > 50cp across 10 diverse positions |

If a gate fails, the UI shows which gate and suggests a rephrasing.

### 3. Play
Drag pieces to move. After every engine move, a narration line appears in the commentary feed and the win probability bar updates live.

### 4. Iterate
Click **Iterate** and refine mid-session:
> *"also make it ignore its own king safety"*

Claude regenerates. Your previous versions are listed in the history panel — click any to start a new game with it.

### 5. Tournament
Click **Tournament** to run a 10-game round-robin against Tal, Karpov, and Petrosian. Results appear as a bar chart and are saved to `tournament/results/`.

---

## Architecture

```
Chess Forge
├── core/                  Rust — UCI engine (negamax + alpha-beta + quiescence + IDDFS)
│   └── --eval-server      Flag: spawns Python eval process, sends FEN, reads centipawns
│
├── eval/
│   ├── eval_server.py     Persistent stdin/stdout bridge (FEN → centipawn integer)
│   ├── generator.py       Claude API → validate → save eval function
│   ├── classic.py         Baseline material + PST eval
│   └── personalities/     Pre-built: tal.py, karpov.py, petrosian.py
│
├── backend/               FastAPI
│   ├── game_manager.py    Spawns Rust + Python processes per game
│   ├── commentary.py      Claude: move + philosophy → one narration sentence
│   ├── odds_engine.py     centipawns_to_prob() sigmoid (Lichess formula)
│   ├── spectator_hub.py   WebSocket fan-out to N viewers
│   └── tournament_runner.py  Round-robin harness + POST /tournament endpoint
│
├── frontend/              React + TypeScript (Vite)
│   └── components/        Board, PhilosophyInput, CodeViewer, EngineInfo,
│                          CommentaryFeed, WinProbBar, TournamentResults, SpectatorRoom
│
└── tournament/results/    JSON match logs per session
```

### Rust ↔ Python Protocol

Rust spawns one persistent Python process per game. For each leaf-node evaluation:

```
Rust → Python:  <FEN string>\n
Python → Rust:  <centipawn integer>\n   (or ERR <message>\n — Rust uses 0 and continues)
Rust → Python:  quit\n                  (on game end)
```

---

## Example Philosophies

### "The Coward"
**Input:** `plays like a coward — avoids all exchanges, retreats pieces, never attacks`
**Interpreted as:** Maximizes king safety and pawn structure integrity; penalizes open files near own king and piece trades.

### "The Gambler"
**Input:** `sacrifices everything for an attack on the enemy king`
**Interpreted as:** Maximizes piece activity toward the enemy king's zone; treats material loss as neutral if king-attack proximity is gained.

> *"The Gambler lunges forward, ignoring the pawn it left hanging — the king is the only prize worth chasing."*

### "The Hoarder"
**Input:** `hoards pawns and never trades queens`
**Interpreted as:** Heavily rewards pawn count and penalizes queen exchanges; treats piece development as secondary to material accumulation.

---

## Tournament Results

*Run `make tournament` to populate. Results saved to `tournament/results/`.*

| Engine | W | D | L | Points |
|--------|---|---|---|--------|
| Tal | — | — | — | — |
| Karpov | — | — | — | — |
| Petrosian | — | — | — | — |
| Classic | — | — | — | — |

---

## How to Read `tournament/results/*.json`

```json
{
  "session_id": "a1b2c3d4",
  "timestamp": "2026-04-24T10:00:00",
  "standings": {
    "Tal":      {"W": 7, "D": 2, "L": 1},
    "Karpov":   {"W": 5, "D": 3, "L": 2}
  },
  "matchups": [
    {"white": "Tal", "black": "Karpov", "result": "white"},
    ...
  ]
}
```

- `standings`: cumulative W/D/L for each engine across all matchups
- `matchups`: one entry per game, in play order
- Points: W=1, D=0.5, L=0

---

## Prompt Iteration Notes

The eval generator uses a two-step Claude prompt. Here is how it evolved during development.

### Step 1 — Interpretation prompt

**v1 (initial):**
```
Restate "{user_description}" as a chess evaluation strategy in one sentence.
```
Problem: vague, produced inconsistent outputs. Move-rule inputs like "only move pawns" generated invalid strategies.

**v2 (final):**
```
Restate as a concrete chess POSITION evaluation strategy expressible as:
"score this board state highly when [X]."
If the input is a move rule (e.g. "only move pawns"), redirect to the closest
positional equivalent and prefix with: "Note: your input was a move rule..."
```
Why: forces position-evaluable output; move-rule redirect prevents architecturally impossible strategies.

### Step 2 — Codegen prompt

**v1 (initial):** Asked for any Python function that "plays like X".
Problem: Claude sometimes used `random`, file I/O, or returned floats. Generated functions weren't deterministic.

**v2 (final):** Added hard rules: import only `chess`/`math`, no side effects, must return `int`, deterministic. Added material reference values (pawn=100, queen=900) so generated weights are calibrated.

---

## Stockfish Benchmark

Run: `make bench`

*Baseline (classic.py) vs Stockfish Skill Level 5, 10 games:*

| Result | Count |
|--------|-------|
| Win | — |
| Draw | — |
| Loss | — |

*Populate after running `make bench`.*

---

## UCI Compatibility

The Rust engine (`core/target/release/chess_forge`) is UCI-compliant. Verified handshake:

```
→ uci
← id name Chess Forge
← uciok
→ isready
← readyok
→ position startpos moves e2e4
→ go movetime 1000
← info depth 6 score cp 30 pv d7d5 ...
← bestmove d7d5
```

Compatible with CuteChess and Arena GUI.

---

## Tests

```bash
make test
```

| Test module | Coverage |
|-------------|---------|
| `test_perft.py` | Move generation node counts (depth 4) |
| `test_eval.py` | Symmetry, material detection, start ≈ 0 |
| `test_generator.py` | All 5 validation gates |
| `test_search.py` | Mate-in-N, obvious captures |
| `test_tournament.py` | Bracket math, W/D/L accounting, JSON output |

---

## API Reference

| Endpoint | Description |
|----------|-------------|
| `POST /generate` | Generate eval from philosophy text |
| `WS /ws/game/{id}` | Player game loop |
| `WS /ws/spectate/{id}` | Spectator view |
| `POST /tournament` | Run round-robin tournament |
| `GET /health` | Liveness check |
