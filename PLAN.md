# Chess Engine Hackathon — Plan

## Team Profile
- 4+ people, multi-day hackathon, experimental/creative ambition, Rust/C++ available

---

## The Big Idea: "Claude Chess Personalities"

Use Claude to generate multiple distinct evaluation functions, each embodying a different chess philosophy (e.g. Tal's aggression, Karpov's positional squeeze, Petrosian's prophylaxis). Run a round-robin tournament between them. Ship the whole thing as a documented, benchmarked experiment.

This hits all four judging criteria simultaneously:
- **Chess quality**: Rust-powered search is fast and strong; Python personalities add variety
- **AI usage**: Claude generates, critiques, and iterates on eval functions; experiments are logged
- **Process**: Two clean parallel streams with clear ownership; streams never block each other
- **Engineering**: Perft tests, self-play benchmarks, UCI compliance, documented prompts

---

## Architecture

```
Chess_cubist/
├── core/                        # Rust — fast, correct, standalone UCI engine
│   ├── src/
│   │   ├── main.rs              # Entry point (UCI loop)
│   │   ├── uci.rs               # UCI protocol interface
│   │   ├── board.rs             # Board representation (shakmaty crate)
│   │   ├── search.rs            # Negamax + alpha-beta + IDDFS + quiescence
│   │   ├── eval.rs              # Material + PST evaluation (Rust-only)
│   │   ├── tt.rs                # Transposition table (Zobrist hashing)
│   │   └── move_order.rs        # MVV-LVA, killer moves, history heuristic
│   └── Cargo.toml
│
├── eval/                        # Python personality engines (each is a UCI engine)
│   ├── base_engine.py           # Base class: UCI loop + negamax using python-chess
│   ├── classic.py               # Material + PST baseline  → run as: python -m eval.classic
│   ├── aggressive.py            # Claude-generated: Tal style → python -m eval.aggressive
│   ├── positional.py            # Claude-generated: Karpov   → python -m eval.positional
│   └── defensive.py             # Claude-generated: Petrosian → python -m eval.defensive
│
├── tournament/
│   ├── self_play.py             # Round-robin between all UCI engines (Python + Rust)
│   ├── vs_stockfish.py          # Benchmark against Stockfish (Skill Level 2/5/8)
│   └── results/                 # JSON match logs + standings
│
├── tests/
│   ├── test_perft.py            # Move generation correctness (node count validation)
│   ├── test_eval.py             # Evaluation unit tests (symmetry, material detection)
│   └── test_search.py           # Search correctness (legal moves, obvious captures)
│
├── prompts/                     # Every Claude interaction, documented
│   ├── eval_aggressive.md       # Prompt + iterations for Tal personality
│   ├── eval_positional.md       # Prompt + iterations for Karpov personality
│   └── eval_defensive.md        # Prompt + iterations for Petrosian personality
│
├── backend/                     # FastAPI — serves game state to the frontend
├── frontend/                    # Next.js — visual board (optional for demo)
├── Makefile                     # Single entry point for all build/test/run commands
├── requirements.txt             # Python deps: chess, pytest
└── pytest.ini                   # Configures test paths and pythonpath
```

### Key integration decision: Python personalities are standalone UCI engines

The plan originally implied that Python eval functions would plug into the Rust search loop. That's complex (requires PyO3 or subprocess FFI) and would couple the two streams.

**Instead**: each personality is a self-contained UCI engine that uses `python-chess` for both move generation and evaluation. The tournament harness connects engines via UCI subprocesses — same protocol as connecting to the Rust engine. This means:

- Stream B can start testing Python vs. Python before any Rust code is written.
- When the Rust engine is ready, it drops in as just another UCI engine in the tournament.
- No cross-language bridging needed at all.

---

## Two Parallel Streams

### Stream A — Rust Engine Core (2 people)

**Phase 1 (hours 1–4)**:
- Initialize Rust project with `shakmaty` (board + legal move gen) and `vampirc-uci` (UCI parsing)
- Implement UCI loop: respond to `uci`, `isready`, `position`, `go`, `quit`
- Implement negamax + alpha-beta with basic material eval
- Milestone: engine plays legal chess in CuteChess/Arena GUI

**Phase 2 (hours 5–8)**:
- Iterative deepening with time management (`go movetime` / `go wtime/btime`)
- Quiescence search (biggest quality jump — prevents horizon blunders)
- Move ordering: MVV-LVA captures first, then killer moves, then history heuristic
- Transposition table with Zobrist hashing

**Rust crates**:
- `shakmaty = "0.27"` — board representation + legal move generation
- `vampirc-uci = "0.11"` — UCI protocol parsing

**Build command**: `cd core && cargo build --release`
**Run command**: `./core/target/release/chess-engine`

**Target**: A UCI-compliant engine playing ~1200–1400 ELO from search depth alone.

---

### Stream B — Experimentation Layer (2 people)

Stream B is unblocked from hour 1 — Python engines are fully functional without the Rust core.

**Phase 1 (hours 1–4)**:
- Implement `eval/base_engine.py`: UCI loop + negamax + alpha-beta using `python-chess`
- Build `eval/classic.py` as the material+PST baseline engine
- Build `tournament/self_play.py`: round-robin harness (connects two UCI engines, runs games, logs results)
- Prompt Claude for each personality — document every prompt in `prompts/`

**Claude Prompt Template**:
```
You are a chess grandmaster with the playing style of [X].
Write a Python class AggressiveEngine(BaseEngine) that overrides the `evaluate(self, board: chess.Board) -> int` method.
The method should return a centipawn score from white's perspective, embodying [X]'s philosophy:
[2-3 sentence description].
Use python-chess for board queries. Positive = white advantage. Import chess at the top.
```

**Personalities**:
| Name | Class | Philosophy |
|------|-------|-----------|
| Classic (baseline) | `ClassicEngine` | Material + classical piece-square tables |
| Aggressive (Tal) | `AggressiveEngine` | Piece activity, open lines toward enemy king, king attack zone bonus |
| Positional (Karpov) | `PositionalEngine` | Outposts, pawn structure, weak squares, piece coordination |
| Defensive (Petrosian) | `DefensiveEngine` | King safety, pawn shield, prophylaxis, penalise hanging pieces |

**Phase 2 (hours 5–8)**:
- Run full round-robin tournament (10 games per matchup, alternate colours)
- When Rust engine is ready, add it to the tournament as `CubistChess`
- Analyse results: which personality wins what type of position?
- Iterate on Claude prompts based on results — document changes and why

**Stockfish strength control**: use `Skill Level` UCI option (not ELO rating).
| Target | Skill Level |
|--------|------------|
| ~ELO 800  | 2 |
| ~ELO 1000 | 5 |
| ~ELO 1200 | 8 |

---

## Build Setup

A root `Makefile` is the single entry point. No one needs to memorise paths or activate venvs manually.

```
make setup         # Install all deps (Rust + Python + Node)
make build         # Compile Rust engine (release mode)
make dev-backend   # Start FastAPI on :8000
make dev-frontend  # Start Next.js on :3000
make test          # Run cargo test + pytest
make tournament    # Run round-robin between personality engines
make bench         # Run vs-Stockfish benchmark
make clean         # Remove build artifacts and venv
```

**First-time setup order**:
1. `make setup` — installs everything
2. `make build` — compiles the Rust engine
3. `make test` — confirm nothing is broken before starting feature work

Python deps (`requirements.txt`): `chess`, `pytest`
Rust deps (declared in `core/Cargo.toml`): `shakmaty`, `vampirc-uci`

---

## Fallback Plan

If the Rust engine is not ready by hour 4, Stream B is unaffected — Python engines run the full tournament. The Rust engine joins later as an additional entrant. This eliminates any blocking dependency between streams.

If Stockfish is not installed on the machine: `brew install stockfish` (Mac) or `apt install stockfish` (Linux).

---

## Testing Strategy

| Test | Purpose | Tool |
|------|---------|------|
| Perft tests | Validate move generation correctness via node counts | python-chess + known perft values |
| Eval unit tests | Symmetry, material detection, starting position near zero | pytest |
| Search tests | Returns legal moves, captures obvious hanging pieces | pytest |
| Self-play ELO | Round-robin between personalities | Custom tournament runner |
| Stockfish benchmark | Win rate vs. Stockfish Skill Level 2/5/8 | python-chess engine API |
| UCI GUI test | Verify engine handshake in CuteChess or Arena | Manual |

---

## Build Order / Milestones

| Milestone | Owner | When |
|-----------|-------|------|
| `base_engine.py` + `classic.py` run as UCI | Stream B | Hour 1 |
| Self-play harness runs (Python vs. Python) | Stream B | Hour 2 |
| UCI Rust stub compiles and responds to `isready` | Stream A | Hour 2 |
| 3 Claude personalities generated + documented | Stream B | Hour 5 |
| Rust engine plays legal chess (negamax + UCI) | Stream A | Hour 4 |
| Quiescence + move ordering done | Stream A | Hour 6 |
| Rust engine entered in tournament | Both | Hour 6 |
| Transposition table integrated | Stream A | Hour 8 |
| Full round-robin results ready | Stream B | Hour 8 |
| Perft + unit tests passing | Both | Day 2 morning |
| README + prompt docs written | Both | Day 2 afternoon |

---

## Stretch Goals

- **lichess-bot**: Connect the engine to lichess and play live rated games (high demo value)
- **Opening book**: Integrate a Polyglot format opening book for the first 10–15 moves
- **Parameter tuning**: Hill-climbing over eval weights using self-play win rate as signal

(NNUE-lite removed — it's a separate project that would dilute focus.)

---

## Engineering Quality Checklist

- [ ] README with setup, architecture, and experiment results
- [ ] Docstrings on all public functions (Rust and Python)
- [ ] `Cargo.toml` and `requirements.txt` / `pytest.ini`
- [ ] `Makefile` with `setup`, `build`, `test`, `tournament`, `bench` targets
- [ ] Perft tests passing at depth 4 on standard positions
- [ ] Eval unit tests passing (symmetry, material, starting position)
- [ ] Self-play tournament results saved to `tournament/results/`
- [ ] Every Claude prompt documented in `prompts/` with iteration notes
- [ ] UCI compatibility verified in CuteChess or Arena GUI
- [ ] Stockfish benchmark results documented (win rate at Skill 2/5/8)
