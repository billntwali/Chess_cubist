# Chess Forge — AI Chess Personality Lab

## The Idea

You describe a chess personality in plain English. Claude writes a live Python evaluation function embodying that philosophy — shown on screen the entire time. You play against your creation. After every engine move, Claude narrates what it just did in the personality's voice. You can iterate ("make it even more reckless") and regenerate mid-session. When you're satisfied, you run your creation in an automated tournament against three classic AI personalities and see where it ranks.

> *"plays like a suicidal gambler — sacrifices everything for an attack"*
> → Claude interprets → generates Python eval → shown live in code viewer
> → Engine plays Nf5: *"The Gambler lunges forward, ignoring the pawn it left hanging — the king is the only prize worth chasing."*
> → Win probability bar shifts as the position sharpens
> → Tournament: your creation vs. Tal, Karpov, Petrosian — 10 games each, results shown

No equivalent exists because it requires LLM code generation at runtime, a live validated eval pipeline, and a narration layer — all simultaneously.

---

## Why This Wins All Four Criteria

| Criterion | How It's Met |
|-----------|-------------|
| Chess quality | Rust engine: alpha-beta + quiescence + IDDFS + move ordering + TT. Eval validated through 5 gates before any game starts. Tournament results show relative strength. |
| AI usage | (1) Claude generates eval code — visible in CodeViewer. (2) Claude narrates every engine move in personality voice. (3) User iterates on prompts based on engine behavior — documented. Three distinct, demonstrable AI touchpoints. |
| Process | Two fully parallel streams with a clean interface contract. Pre-built personalities (Tal, Karpov, Petrosian) mean Stream B runs tournaments before Rust is done. |
| Engineering | Eval validation pipeline (5 gates), perft tests, mate-in-N tests, round-robin benchmarks, UCI compliance, prompt library with iteration notes. |

---

## Architecture

```
chess_forge/
├── core/                          # Rust — UCI-compliant search engine
│   └── src/
│       ├── search.rs              # Negamax + alpha-beta + quiescence + IDDFS
│       ├── tt.rs                  # Transposition table (Zobrist hashing)
│       ├── move_order.rs          # MVV-LVA, killer moves, history heuristic
│       └── uci.rs                 # UCI protocol + --eval-server flag
│
├── eval/
│   ├── eval_server.py             # Persistent stdin/stdout eval bridge (Rust ↔ Python)
│   ├── classic.py                 # Baseline material + PST eval
│   ├── generator.py               # Claude API → eval function + 5-gate validation
│   ├── generated/                 # Runtime-created evals (uuid_slug.py)
│   └── personalities/             # Pre-built classic evals for tournament
│       ├── tal.py                 # Maximizes piece activity + king attack zone
│       ├── karpov.py              # Outposts, pawn structure, weak squares
│       └── petrosian.py           # King safety, pawn shield, prophylaxis
│
├── backend/
│   ├── main.py
│   ├── game_manager.py            # Spawns Rust + Python processes per game
│   ├── spectator_hub.py           # WebSocket fan-out: one game → N viewers
│   ├── commentary.py             # Claude: move + philosophy → one-sentence narration
│   ├── odds_engine.py             # centipawns → win probability sigmoid
│   └── tournament_runner.py      # Round-robin harness using UCI subprocess API
│
├── frontend/
│   └── src/components/
│       ├── PhilosophyInput.tsx    # Text input + Generate button + iteration history
│       ├── Board.tsx              # react-chessboard, drag-and-drop
│       ├── CodeViewer.tsx         # Syntax-highlighted generated eval, live
│       ├── EngineInfo.tsx         # Depth, score, principal variation
│       ├── CommentaryFeed.tsx     # Rolling post-move narration from Claude
│       ├── WinProbBar.tsx         # Live probability bar (updates each move)
│       ├── SpectatorRoom.tsx      # Shareable room link + viewer count
│       └── TournamentResults.tsx  # Bar chart: user's personality vs. classics
│
├── tournament/
│   └── results/                   # JSON match logs + standings
│
├── tests/
│   ├── test_perft.py
│   ├── test_eval.py
│   ├── test_generator.py
│   └── test_search.py
│
├── prompts/
│   ├── eval_generator.md          # Two-step prompt: interpretation → codegen
│   └── commentary.md             # Post-move narration system prompt
│
├── Makefile                       # setup / build / test / tournament / bench
└── README.md
```

---

## Rust-Python Interface Contract

Rust spawns one persistent Python process at game start. For each leaf-node eval, Rust writes a FEN to stdin; Python returns a centipawn integer. On game end, Rust sends `quit`.

### eval_server.py (Stream B owns)

```python
import sys, chess, importlib.util

def load_eval(path):
    spec = importlib.util.spec_from_file_location("eval_fn", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.evaluate

if __name__ == "__main__":
    evaluate = load_eval(sys.argv[1])
    for line in sys.stdin:
        line = line.strip()
        if not line: continue
        if line == "quit": break
        try:
            print(int(evaluate(chess.Board(line))), flush=True)
        except Exception as e:
            print(f"ERR {e}", flush=True)
```

### Protocol

| Direction | Message |
|-----------|---------|
| Rust → Python | FEN string + `\n` |
| Python → Rust | Integer centipawns + `\n` |
| Rust → Python | `quit\n` |
| Python → Rust (error) | `ERR <message>\n` (Rust uses 0, logs, continues) |

Rust spawned via: `./core/target/release/chess_forge --eval-server "python eval/eval_server.py <eval_path>"`

If Python process is unavailable or returns ERR: Rust falls back to built-in material eval.

---

## The Odds Engine

```python
def centipawns_to_prob(cp: int) -> float:
    """Standard chess win probability (white's perspective). Used by Lichess + TCEC."""
    return 1 / (1 + 10 ** (-cp / 400))
```

After each move the backend emits `{move, fen, eval_cp, white_prob}` to all connected clients. The WinProbBar updates live. No betting — just a real-time read on who's winning.

---

## The Claude Prompts

### Step 1 — Interpretation (`prompts/eval_generator.md`)
```
The user wants a chess engine with this philosophy: "{user_description}"

Restate this as a concrete chess POSITION evaluation strategy in one sentence —
something expressible as: "score this board state highly when [X]."

Use only chess concepts: piece activity, king safety, pawn structure, material
balance, mobility, open files, outposts, etc.

If the input describes a move rule (e.g. "only move pawns"): redirect to the
closest positional philosophy and prefix with:
"Note: your input was a move rule — here's the closest positional equivalent:"

Return ONLY the one-sentence restatement.
```

### Step 2 — Codegen (`prompts/eval_generator.md`, continued)
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

### Post-Move Commentary (`prompts/commentary.md`)
```
Chess engine playing "{philosophy}" just played {san} in this position: {fen}
Engine evaluation: {cp} centipawns (positive = White better).

Write ONE vivid sentence narrating this move as if the philosophy is acting.
Do not mention centipawns or evaluation scores. Be concise and dramatic.
```

---

## Eval Validation Pipeline (5 gates, in order)

| Gate | Check | Method |
|------|-------|--------|
| Syntax | Parses as valid Python | `ast.parse()` |
| Safety | No banned names: `os`, `subprocess`, `open`, `eval`, `exec`, `random`, `time`, `__import__` | AST node visitor |
| Sanity | Start pos ≈ 0 ±50cp; White up queen > 200cp; Black up queen < −200cp | 3 canonical FENs |
| Determinism | Same FEN returns identical score twice | `eval(pos) == eval(pos)` on 3 positions |
| Variance | Std dev across 10 diverse positions > 50cp | Catches near-constant evals |

Failure: UI shows which gate failed, raw Claude output, and a suggested rephrasing.

---

## Tournament Mode

```
tournament_runner.py --engines user_eval.py tal.py karpov.py petrosian.py --games 10
```

- Round-robin: each pair plays 10 games (5 as white, 5 as black), alternating colors
- Results saved to `tournament/results/{session_id}.json`
- TournamentResults.tsx renders a bar chart of win rates
- Stockfish Skill Level 5 included as calibration reference (not shown in main chart)

Pre-built personalities (Stream B generates these via Claude before the hackathon, using LLM-PLAN1's prompt template):
- `tal.py` — Piece activity, open lines toward king, attack zone bonus
- `karpov.py` — Outposts, weak squares, bishop pair, pawn structure integrity
- `petrosian.py` — King safety, pawn shield, prophylaxis, penalize hanging pieces

---

## User Flow

1. Land on the app — see a chessboard, a text input, and three preset personalities listed
2. Type: *"A bloodthirsty attacker that sacrifices pawns to open files toward the enemy king"*
3. Click **Interpret** → Claude shows: *"Maximizes open file bonuses toward the enemy king's position, treats pawn sacrifices as neutral if they gain file access"*
4. Adjust if needed → click **Generate** → spinner → Python code appears in CodeViewer
5. All 5 gates pass (shown as green checkmarks)
6. Click **Play** → choose color → WebSocket game starts
7. After each engine move: a narration line appears in the CommentaryFeed; win probability bar shifts
8. Click **Iterate** mid-game: *"also make it ignore its own king safety"* → regenerated → new game
9. Iteration history panel shows all past versions — click any to start a new game with it
10. Click **Tournament** → runs 10-game round-robin vs. Tal/Karpov/Petrosian → bar chart shows results
11. Share room link → friend watches the tournament live, sees the same board + commentary + probability bar

---

## Two Parallel Streams

### Stream A — Rust Engine + Eval Bridge
- UCI-compliant engine: `shakmaty` + `vampirc-uci`
- Negamax + alpha-beta + quiescence + IDDFS
- Transposition table (Zobrist hashing)
- MVV-LVA + killer moves + history heuristic
- `--eval-server <cmd>` flag: spawns Python process, uses stdin/stdout protocol
- Fallback to built-in material eval on ERR or process death
- After each move: emit `{move, fen, eval_cp, pv}` via WebSocket to backend

### Stream B — Generator + Frontend + Experiment
- `eval/eval_server.py` + `eval/generator.py` + validation pipeline
- Pre-built classic personalities (`tal.py`, `karpov.py`, `petrosian.py`) via Claude
- `commentary.py`: post-move Claude narration
- `odds_engine.py`: centipawns → win probability
- `spectator_hub.py`: WebSocket fan-out to N viewers
- `tournament_runner.py`: round-robin harness
- FastAPI: `/generate`, `/ws/game/{id}`, `/ws/spectate/{id}`, `/tournament`
- Full React frontend

**Interface dependency**: Stream B verifies `eval_server.py` standalone before integration:
```bash
echo "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1" | python eval/eval_server.py eval/classic.py
# expected: integer near 0
```
Stream A verifies Rust caller with a mock Python script that echoes `42` for any FEN.

---

## Build Order / Milestones

| Milestone | Owner | When |
|-----------|-------|------|
| UCI engine plays legal chess (built-in eval) | Stream A | Hour 3 |
| `eval_server.py` testable standalone | Stream B | Hour 3 |
| `/generate` endpoint + 5-gate validation | Stream B | Hour 4 |
| Rust `--eval-server` working with mock Python | Stream A | Hour 4 |
| Classic personalities generated + tested in tournament | Stream B | Hour 4 |
| **Integration: Rust + Python eval server end-to-end** | Both | Hour 5 |
| Engine emits eval_cp after each move | Stream A | Hour 5 |
| WebSocket game loop + WinProbBar in browser | Both | Hour 6 |
| Quiescence + move ordering done | Stream A | Hour 6 |
| CommentaryFeed working (Claude narration) | Stream B | Hour 7 |
| CodeViewer + iteration history in UI | Stream B | Hour 7 |
| Transposition table integrated | Stream A | Hour 8 |
| Tournament mode end-to-end (TournamentResults.tsx) | Both | Hour 8 |
| SpectatorRoom sharing working | Stream B | Hour 8 |
| Perft + eval + generator tests passing | Both | Day 2 morning |
| README + prompt docs with iteration notes written | Both | Day 2 afternoon |

---

## Testing

| Test | Purpose |
|------|---------|
| Perft depth 4 | Move generation correctness (node count validation) |
| Mate-in-N (20 puzzles) | Search finds forced mates |
| `test_eval.py` — symmetry, material, start pos ≈ 0 | Classic eval sanity |
| `test_generator.py` — all 5 validation gates | Generated evals are safe and sane |
| `eval_server.py` standalone | FEN in → integer out, ERR on bad input |
| Eval determinism | Same position returns same score twice |
| Eval variance (10 diverse FENs) | Eval is position-sensitive, not constant |
| Odds engine sanity | 0cp → 50%, +400cp → ~90%, −400cp → ~10% |
| Tournament harness | Runs to completion, logs correct W/D/L counts |
| End-to-end latency | Move → commentary → UI update in <2s |
| UCI GUI test | Engine handshake verified in CuteChess or Arena |

---

## Stretch Goals (in priority order)

1. **"Why did it play that?"** — after each engine move, one paragraph from Claude explaining the move in relation to the stated philosophy (richer than one-sentence narration)
2. **Heatmap overlay** — highlight squares red/green based on the eval function's output gradient (visual intelligence borrowed from Chess Commander)
3. **Export your engine** — download the generated eval + Rust binary as a standalone UCI engine, play it on lichess-bot
4. **Prompt iteration log** — show a visual diff between v1 and v2 of the philosophy, highlighting what changed in the generated code

---

## Engineering Quality Checklist

- [ ] README: setup, architecture, example philosophies, how to read tournament results
- [ ] `prompts/eval_generator.md` and `prompts/commentary.md` with iteration notes
- [ ] `Makefile`: `setup`, `build`, `test`, `tournament`, `bench` targets
- [ ] Perft tests passing at depth 4
- [ ] Mate-in-N tests passing
- [ ] `test_generator.py` covering all 5 validation gates
- [ ] Tournament results for classic personalities saved to `tournament/results/`
- [ ] `eval_server.py` standalone test documented
- [ ] UCI compatibility verified in CuteChess or Arena
- [ ] Stockfish Skill 5 benchmark result documented in README
