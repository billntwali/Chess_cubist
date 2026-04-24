# Chess Engine Hackathon — Plan

## Team Profile
- 4+ people, multi-day hackathon, experimental/creative ambition, Rust/C++ available

---

## The Big Idea: "Claude Chess Personalities"

Use Claude to generate multiple distinct evaluation functions, each embodying a different chess philosophy (e.g. Tal's aggression, Karpov's positional squeeze, Petrosian's prophylaxis). Run a round-robin tournament between them. Ship the whole thing as a documented, benchmarked experiment.

This hits all four judging criteria simultaneously:
- **Chess quality**: Rust-powered search is fast and strong
- **AI usage**: Claude generates, critiques, and iterates on eval functions; experiments are logged
- **Process**: Two clean parallel streams with clear ownership
- **Engineering**: Perft tests, self-play benchmarks, UCI compliance, documented prompts

---

## Architecture

```
chess_engine/
├── core/                        # Rust — fast, correct, UCI-compliant
│   ├── src/
│   │   ├── board.rs             # Board representation (shakmaty crate)
│   │   ├── search.rs            # Negamax + alpha-beta + IDDFS + quiescence
│   │   ├── tt.rs                # Transposition table (Zobrist hashing)
│   │   ├── move_order.rs        # MVV-LVA, killer moves, history heuristic
│   │   └── uci.rs               # UCI protocol interface
│   └── Cargo.toml
│
├── eval/                        # Pluggable evaluation functions (Python)
│   ├── classic.py               # Hand-coded material + PST baseline
│   ├── aggressive.py            # Claude-generated: values king attack, sacrifices
│   ├── positional.py            # Claude-generated: values pawn structure, weak squares
│   └── defensive.py            # Claude-generated: values king safety, prophylaxis
│
├── tournament/
│   ├── self_play.py             # Round-robin engine vs. engine
│   ├── vs_stockfish.py          # Benchmark against Stockfish at ELO 800/1000/1200
│   └── results/                 # JSON + visualizations of match results
│
├── tests/
│   ├── test_perft.py            # Move generation correctness (node count validation)
│   ├── test_eval.py             # Evaluation unit tests
│   └── test_search.py           # Mate-in-N correctness
│
├── prompts/                     # Every Claude interaction, documented
│   ├── eval_aggressive.md
│   ├── eval_positional.md
│   └── eval_defensive.md
│
└── README.md
```

---

## Two Parallel Streams

### Stream A — Rust Engine Core (2 people)

**Phase 1 (hours 1–4)**:
- Initialize Rust project with `shakmaty` (board + legal move gen) and `vampirc-uci` (UCI parsing)
- Implement negamax with alpha-beta pruning
- Implement UCI protocol — unlocks GUI testing immediately
- Basic material-count evaluation (enough to play legal chess)

**Phase 2 (hours 5–8)**:
- Iterative deepening with time management
- Quiescence search (prevents tactical blunders — huge quality jump)
- Move ordering: MVV-LVA captures, killer moves, history heuristic
- Transposition table with Zobrist hashing

**Rust crates**:
- `shakmaty` — board representation + legal move generation
- `vampirc-uci` — UCI protocol parsing

**Target**: A UCI-compliant engine playing ~1200–1400 ELO purely from search depth, with evaluation pluggable.

---

### Stream B — Experimentation Layer (2 people)

**Phase 1 (hours 1–4)**:
- Python self-play harness using `python-chess` (connect two UCI engines, run games, collect results)
- Benchmark baseline engine vs. Stockfish at ELO 800/1000/1200
- Prompt Claude to generate evaluation function personalities — document each prompt and iteration

**Claude Prompt Template**:
```
You are a chess grandmaster with the playing style of [X].
Write a Python function `evaluate(board: chess.Board) -> int` that returns
a centipawn score from white's perspective. The function should embody [X]'s philosophy:
[2-3 sentence description].
Use python-chess for board queries. Positive = white advantage.
```

**Personalities**:
| Name | Philosophy |
|------|-----------|
| Aggressive (Tal) | Overvalues piece activity, open lines toward enemy king, accepts material sacrifices |
| Positional (Karpov) | Overvalues outposts, weak enemy pawns, piece coordination, long-term pressure |
| Solid (Petrosian) | Overvalues king safety, prophylaxis, avoids pawn weaknesses at all costs |
| Materialist | Pure material counting + classical PSTs — the baseline for comparison |

**Phase 2 (hours 5–8)**:
- Run full round-robin tournament (10+ games per matchup, log all results)
- Analyze: which personality wins what type of position?
- Iterate on Claude prompts based on results — document what changed and why
- Optional stretch: simple NNUE-lite (3-layer PyTorch net trained on self-play data)

---

## Testing Strategy

| Test | Purpose | Tool |
|------|---------|------|
| Perft tests | Validate move generation correctness via node counts | python-chess + known perft values |
| Mate-in-N positions | Verify search finds forced mates | ~20 tactical puzzles |
| Self-play ELO | Round-robin between personalities | Custom tournament runner |
| Stockfish benchmark | Win rate vs. Stockfish ELO 800/1000/1200 | python-chess Stockfish wrapper |
| Eval unit tests | Sanity check evaluation function (e.g., empty board = 0) | pytest |

---

## Build Order / Milestones

| Milestone | Owner | When |
|-----------|-------|------|
| UCI engine plays legal chess | Stream A | End of hour 3 |
| Self-play harness runs | Stream B | End of hour 3 |
| Quiescence + move ordering done | Stream A | End of hour 6 |
| 3 Claude eval personalities generated | Stream B | End of hour 5 |
| Transposition table integrated | Stream A | End of hour 8 |
| Tournament results ready | Stream B | End of hour 8 |
| Perft + unit tests passing | Both | Day 2 morning |
| README + prompt docs written | Both | Day 2 afternoon |

---

## Stretch Goals

- **NNUE-lite**: Train a 3-layer neural net on self-play data, compare ELO vs. classical eval
- **lichess-bot**: Connect the engine to lichess and play live rated games
- **Opening book**: Integrate a Polyglot format opening book for the first 10-15 moves
- **Parameter tuning**: SPSA or hill-climbing over eval weights using self-play win rate as signal

---

## Engineering Quality Checklist

- [ ] README with setup, architecture, and experiment results
- [ ] Docstrings on all public functions (Rust and Python)
- [ ] `Cargo.toml` and `requirements.txt` / `pyproject.toml`
- [ ] Perft tests passing at depth 4 on standard positions
- [ ] Mate-in-N tests passing
- [ ] Self-play tournament results saved to `tournament/results/`
- [ ] Every Claude prompt documented in `prompts/`
- [ ] UCI compatibility verified in at least one GUI (Arena, CuteChess, etc.)
