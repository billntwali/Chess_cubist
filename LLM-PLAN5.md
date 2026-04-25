# Chess Stakes — Live Prediction Markets for Chess

## Context

The user wants to add a Kalshi/Polymarket-style live betting layer to the chess engine hackathon project. The strongest approach is to keep the LLM-PLAN4 philosophy-driven engine as the technical core and wrap it in a social spectator/betting product. This surfaces the AI usage visibly, adds a demo-friendly "wow" moment (live odds bar updating after every move), and gives judges a genuinely novel product: a chess betting platform where the "house" odds are powered by your own engine's evaluation.

---

## The Product: "Chess Stakes"

Chess meets Kalshi. Two modes:

**Mode 1 — AI Philosophy Showdown (Core)**
1. Creator generates Philosophy A and B via natural language → Claude writes custom eval functions
2. A shareable spectator room link is created
3. Friends join, get 1,000 play chips, and place bets: pick the winner, over/under on move count
4. The two AI engines play — win probability bar updates live after every move, Claude narrates each move in each philosophy's "voice"
5. Game ends → payouts distributed based on odds locked in at bet time (Kalshi-style)

**Mode 2 — Lichess Human Match**
1. Enter two Lichess usernames
2. Claude fetches game history + ELO, profiles each player's style (aggressive/defensive/positional), sets opening odds
3. Friends join spectator room, bet on the match
4. Engine evaluates each position live, updates odds; commentary explains the eval in plain language
5. Payouts on game end

---

## Architecture

```
chess_stakes/
├── core/                          # Rust — UCI engine (from LLM-PLAN4, unchanged)
│   └── src/
│       ├── board.rs
│       ├── search.rs              # Negamax + alpha-beta + quiescence + IDDFS
│       ├── tt.rs
│       ├── move_order.rs
│       └── uci.rs
│
├── eval/                          # Python eval layer (from LLM-PLAN4)
│   ├── eval_server.py             # Persistent stdin/stdout eval process
│   ├── classic.py                 # Baseline material eval
│   └── generator.py              # Claude API → validated eval function
│
├── backend/                       # FastAPI
│   ├── main.py
│   ├── game_manager.py            # Spawns Rust processes per game
│   ├── spectator_hub.py           # WebSocket fan-out: one game → N viewers
│   ├── betting_manager.py         # Chip store, markets, bet locking, payouts
│   ├── odds_engine.py             # centipawns → win probability (sigmoid)
│   ├── lichess_client.py          # Lichess API: user stats, game history, streaming
│   ├── player_profiler.py         # Claude: style analysis → opening odds (Mode 2)
│   └── commentary.py             # Claude: move + philosophy → one-sentence narration
│
├── frontend/                      # React + TypeScript
│   └── src/components/
│       ├── PhilosophySetup.tsx    # Generate two personalities (Mode 1 setup)
│       ├── LichessSetup.tsx       # Enter usernames + show style profile (Mode 2 setup)
│       ├── Board.tsx
│       ├── WinProbBar.tsx         # Live probability bar (updates each move)
│       ├── BettingPanel.tsx       # Place bets, chip balance, locked markets display
│       ├── CommentaryFeed.tsx     # Rolling Claude narration
│       ├── SpectatorRoom.tsx      # Room wrapper: spectator count, share link
│       └── CodeViewer.tsx         # Shows generated eval code (Mode 1)
│
├── prompts/
│   ├── eval_generator.md          # (from LLM-PLAN4)
│   ├── player_profiler.md         # Style analysis + opening odds system prompt
│   └── commentary.md             # Move narration system prompt
│
└── tests/
    ├── test_perft.py
    ├── test_odds_engine.py
    ├── test_betting_manager.py
    └── test_generator.py
```

---

## The Odds Engine (`backend/odds_engine.py`)

Standard chess win probability sigmoid — same formula used by Lichess and TCEC:

```python
def centipawns_to_prob(cp: int) -> float:
    """Win probability for White. cp > 0 means White is better."""
    return 1 / (1 + 10 ** (-cp / 400))

def market_odds(cp: int) -> dict:
    p = centipawns_to_prob(cp)
    return {
        "white_win": round(p, 4),
        "black_win": round(1 - p, 4),
        "payout_white": round(1 / p, 2),   # chips returned per chip bet
        "payout_black": round(1 / (1 - p), 2),
    }
```

Odds lock after move 10. Payouts use odds at time of bet (early correct bets earn more).

---

## Betting Manager (in-memory, no DB needed)

```
Room state:
  room_id → {
    markets: {
      "winner": {bets: [{user, side, chips, odds_at_bet}], locked: bool},
      "over_40_moves": {bets: [...], locked: bool},
    },
    chips: {user_id: int},   # starts at 1000
    result: None | "white" | "black"
  }
```

- Bet placement: subtract chips, append to market, record odds_at_bet
- Lock trigger: move 10 reached → all markets locked
- Payout: winner bets split the total loser pool proportionally to bet size × odds_at_bet

---

## Claude Prompts

**Player Profiler** (`prompts/player_profiler.md`):
```
Given this Lichess player:
  Username: {username}, ELO: {elo}, Win rate: {win_rate}%
  Most common openings: {openings}
  Recent 10 games: {outcomes}

Describe their style in 2 sentences. Then estimate win probability vs opponent
(ELO {opp_elo}, style: "{opp_style}").
Return JSON only: {"style": "...", "win_probability": 0.XX, "reasoning": "..."}
```

**Commentary** (`prompts/commentary.md`):
```
Chess engine playing "{philosophy}" just played {san} in this position: {fen}
Engine evaluation: {cp} centipawns (positive = White better).

Write ONE vivid sentence narrating this move as if the philosophy is acting.
Do not mention centipawns or engine scores. Be concise and dramatic.
```

---

## Two Parallel Streams

### Stream A — Rust Engine + Odds Broadcast
- Port Rust UCI engine from LLM-PLAN4 (unchanged)
- After each move: emit `{move, fen, eval_cp, pv}` to backend via WebSocket
- `odds_engine.py` converts eval_cp → probability, fans out to all spectators via `spectator_hub.py`
- Mode 2: `lichess_client.py` streams a live game via `GET /api/stream/game/{id}` (Lichess NDJSON API), feeds positions to the engine for evaluation

### Stream B — Betting Platform + Frontend
- `betting_manager.py`: chip store, bet placement, market locking, payout calculation
- `player_profiler.py`: Lichess API fetch → Claude style analysis → JSON odds
- `commentary.py`: post-move Claude narration call, streamed to CommentaryFeed
- `spectator_hub.py`: WebSocket hub, one game broadcasts to N concurrent viewers
- React frontend: BettingPanel, WinProbBar, SpectatorRoom, CommentaryFeed

**Interface dependency**: `spectator_hub.py` must be testable standalone before integration (send mock `{eval_cp: 50}` and verify all connected clients receive it).

---

## Build Order / Milestones

| Milestone | Owner | When |
|-----------|-------|------|
| UCI engine plays legal chess (LLM-PLAN4 port) | Stream A | Hour 3 |
| `eval_server.py` testable standalone | Stream B | Hour 3 |
| `/generate` endpoint + eval validation pipeline | Stream B | Hour 4 |
| `odds_engine.py` unit tested | Stream A | Hour 4 |
| Engine emits eval after each move via WebSocket | Stream A | Hour 5 |
| `spectator_hub.py` fan-out tested (2 clients) | Stream B | Hour 5 |
| **Integration: live board + win probability bar in browser** | Both | Hour 6 |
| `betting_manager.py` tested (place, lock, payout) | Stream B | Hour 6 |
| BettingPanel + WinProbBar in React | Stream B | Hour 7 |
| Commentary feed working (Claude post-move narration) | Stream B | Hour 7 |
| Mode 2: Lichess usernames → profile → opening odds | Stream A | Hour 8 |
| Full Mode 1 demo end-to-end | Both | Hour 8 |
| Perft, odds, betting, generator tests passing | Both | Day 2 morning |
| README + prompt docs written | Both | Day 2 afternoon |

---

## Testing

| Test | Purpose |
|------|---------|
| Perft depth 4 | Move generation correctness |
| `test_odds_engine.py` | Centipawn → probability sanity (0cp ≈ 50%, +400cp ≈ 90%) |
| `test_betting_manager.py` | Chip math, market locking at move 10, payout distribution |
| Eval sanity (3 canonical FENs) | Generated evals return sane scores |
| Generator pipeline | Claude output passes all 5 validation gates |
| `spectator_hub.py` | N clients all receive broadcast within 100ms |
| End-to-end latency | Move → commentary → odds update in browser in <2s |

---

## Stretch Goals

- **Live pro game mode**: Stream a live Lichess tournament game, open public betting room
- **Move market**: Bet on the exact next move (high risk, 20× payout)
- **Personality export**: Download generated AI as standalone UCI engine + play on lichess-bot
- **Chip leaderboard**: Track balances across sessions, show on landing page

---

## Engineering Quality Checklist

- [ ] README: setup, architecture, how betting markets work, how to generate personalities
- [ ] `prompts/` directory with all three templates fully documented
- [ ] Perft tests passing at depth 4
- [ ] `test_odds_engine.py` and `test_betting_manager.py` with edge cases
- [ ] `eval_server.py` standalone testable (echo test from LLM-PLAN4)
- [ ] WebSocket spectator hub tested with ≥2 concurrent clients
- [ ] UCI compatibility verified in Arena or CuteChess
