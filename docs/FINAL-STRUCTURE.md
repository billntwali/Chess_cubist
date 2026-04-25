# Chess Forge — Team Structure (5 People)

## Person 1 — Rust Engine

**Owns:** `core/`

- UCI loop (`uci.rs`) — handshake, `position`, `go`, `stop`
- Legal move generation via `shakmaty`
- Negamax + alpha-beta + quiescence + IDDFS (`search.rs`)
- Transposition table with Zobrist hashing (`tt.rs`)
- MVV-LVA + killer moves + history heuristic (`move_order.rs`)
- `--eval-server <cmd>` flag: spawns Python subprocess, uses the stdin/stdout FEN protocol
- Fallback to built-in material eval on `ERR` or process death
- After each move: emits `{move, fen, eval_cp, pv}` to backend

**Tests:** perft depth 4, mate-in-N (20 puzzles), UCI handshake in CuteChess or Arena

**Integration seam:** verify Rust caller with a mock Python that echoes `42` for any FEN before integrating with Person 2

---

## Person 2 — Claude Eval Generator + Validation

**Owns:** `eval/` + `prompts/`

- `eval_server.py` — persistent stdin/stdout bridge (FEN → centipawn integer)
- `generator.py` — two-step Claude API calls: interpret philosophy → generate `evaluate(board)`
- `validator.py` — all 5 gates (syntax, safety, sanity, determinism, variance)
- `classic.py` — baseline material + PST fallback eval
- Pre-built personalities generated via Claude: `tal.py`, `karpov.py`, `petrosian.py`
- `prompts/eval_generator.md` — both prompt steps, with iteration notes logged

**Tests:** `test_generator.py` (all 5 gates), `test_eval.py` (symmetry, material, start ≈ 0), standalone eval_server test

**Integration seam:** `echo "<FEN>" | python eval/eval_server.py eval/classic.py` must return an integer near 0 — Person 3 depends on this before wiring the backend

---

## Person 3 — Backend + Game Orchestration

**Owns:** `backend/`

- `main.py` — FastAPI app, routes: `/generate`, `/ws/game/{id}`, `/ws/spectate/{id}`, `/tournament`
- `game_manager.py` — spawns one Rust process + one Python eval_server process per game
- `commentary.py` — post-move Claude call: move + philosophy + FEN → one vivid narration sentence
- `odds_engine.py` — `centipawns_to_prob(cp)` sigmoid, emits `{move, fen, eval_cp, white_prob}` to all clients after each move
- `spectator_hub.py` — WebSocket fan-out: one live game → N viewers

**Tests:** odds engine sanity (0cp → 50%, ±400cp → ~90%/~10%), end-to-end latency < 2s (move → commentary → UI update)

**Integration seam:** Person 1's engine must be emitting `eval_cp` per move; Person 5's frontend consumes the WebSocket

---

## Person 4 — Tournament + Docs + DevOps

**Owns:** `tournament/`, `Makefile`, `README.md`

- `tournament_runner.py` — round-robin harness, spawns Rust + Python per pairing, alternates colors, 10 games per pair
- `/tournament` endpoint integration with Person 3's backend
- Results saved to `tournament/results/{session_id}.json`
- Stockfish Skill Level 5 benchmark (calibration reference, documented in README)
- `Makefile` targets: `setup`, `build`, `test`, `tournament`, `bench`
- `README.md` — setup, architecture diagram, example philosophies, how to read tournament results, prompt iteration notes, Stockfish benchmark result
- UCI compatibility documented

**Tests:** tournament harness runs to completion, logs correct W/D/L counts; verify bracket math

**Integration seam:** depends on Person 2's classic personalities being testable standalone before integration with the full stack

---

## Person 5 — Frontend

**Owns:** `frontend/src/components/`

- `PhilosophyInput.tsx` — text input, Interpret button, Generate button, iteration history panel
- `Board.tsx` — `react-chessboard`, drag-and-drop, highlights last move
- `CodeViewer.tsx` — syntax-highlighted generated eval, live-updated on iteration
- `EngineInfo.tsx` — depth, score, principal variation
- `CommentaryFeed.tsx` — rolling post-move narration lines from Claude
- `WinProbBar.tsx` — live probability bar, updates each move via WebSocket
- `TournamentResults.tsx` — bar chart of win rates (user's engine vs. Tal/Karpov/Petrosian)
- `SpectatorRoom.tsx` — shareable room link + viewer count badge

**Tests:** visual golden path — generate an engine, play 5 moves, check commentary appears and probability bar moves

**Integration seam:** consumes `/ws/game/{id}` and `/ws/spectate/{id}` from Person 3; calls `/generate` from Person 2 via Person 3's API

---

## Integration Timeline (shared)

| Hour | Milestone | Owners |
|------|-----------|--------|
| 3 | Rust plays legal chess (built-in eval); `eval_server.py` testable standalone | P1, P2 |
| 4 | `/generate` + 5-gate validation live; Rust `--eval-server` working with mock Python; classic personalities done | P1, P2, P4 |
| 5 | **Integration: Rust + Python eval server end-to-end** | P1 + P2 |
| 5–6 | WebSocket game loop + WinProbBar in browser | P3 + P5 |
| 7 | CommentaryFeed working; CodeViewer + iteration history | P3, P5 |
| 8 | Tournament end-to-end; SpectatorRoom sharing | P3, P4, P5 |
| Day 2 morning | All tests passing | P1, P2, P3, P4, P5 |
| Day 2 afternoon | README + prompt docs finalized | P4 |

The critical seam is **Hour 5**: Person 1 and Person 2 must both have their standalone pieces verified before integrating. Everything else can proceed in parallel without blocking.
