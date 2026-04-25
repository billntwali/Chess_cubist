# Chess Cubist Hackathon Plan Review

This document summarizes the current plan files, evaluates the pros and cons of each idea, and proposes one integrated hackathon-worthy direction.

## Hackathon Judging Criteria

The hackathon, as described in `CLAUDE.md`, rewards four areas:

- **Chess engine quality**: legal, strategic chess; correctness matters, but perfection is not required.
- **AI usage**: clear evidence of using Claude, critically evaluating generated code, iterating, and running experiments.
- **Process and parallelization**: smart team division, parallel workstreams, code review, and integration evidence.
- **Engineering quality**: documentation, tests, prior-art research, UCI support, self-play benchmarks, and Stockfish comparison.

## Plan-by-Plan Review

## LLM-PLAN1: Claude Chess Personalities

### Idea

Use Claude to generate multiple chess evaluation personalities, such as aggressive, positional, defensive, and materialist. Run them in a round-robin tournament and benchmark the results.

### Pros

- Very feasible for a hackathon.
- Strong testing and rigor story: self-play tournaments, Stockfish benchmarks, perft tests.
- Good parallelization: one team can build the Rust engine while another builds Python personality engines and tournament tooling.
- Easy for judges to understand.
- Produces measurable results and documentation.

### Cons

- Less interactive than the other ideas.
- "Different chess bots with personalities" is fun but not especially shocking.
- Claude usage is mostly offline generation rather than deeply embedded in the live product.
- The demo may feel more like an experiment than a product.

## PLAN3: Chess Commander

### Idea

Users do not move pieces directly. Instead, they give natural-language strategic commands, such as "lock down the center and prepare a queenside expansion." Claude translates those commands into engine evaluation weights, and the engine chooses the move.

### Pros

- Highly creative and distinct from standard chess platforms.
- Makes the engine feel interactive at the decision-making level.
- Claude has a meaningful role as a translator from vague strategy to concrete engine parameters.
- Strong demo moment: a user gives an order and the engine changes behavior.
- Good product framing: chess as command rather than piece dragging.

### Cons

- Natural-language strategic commands can be ambiguous.
- Hard to prove that the engine actually followed the strategy.
- If the engine blunders tactically, the command illusion breaks.
- More UI/product risk than a pure engine or tournament system.
- Per-move Claude calls can add latency and fragility.

## LLM-PLAN2: Build Your Opponent

### Idea

The user describes a chess philosophy in plain English. Claude generates a live `evaluate(board)` function. The user can inspect the code, play against the generated engine, and iterate on it.

### Pros

- The strongest core product idea.
- User-created engines are meaningfully different from Chess.com-style bots.
- Claude usage is visible and central: it generates real evaluation code.
- Showing the generated code gives judges a concrete artifact.
- The validation pipeline creates a strong engineering story.
- Iteration is natural: "make it more aggressive," "make it hate queen trades," and so on.

### Cons

- Runtime code generation is risky unless validation and sandboxing are handled carefully.
- Integrating generated Python evals with a Rust search engine adds complexity.
- Search may become slow if the Rust engine calls Python too often.
- Needs careful scope control to avoid becoming too many systems at once.

## LLM-PLAN3: Build Your Opponent With Interface Contract

### Idea

This refines Plan 2 by specifying a Rust/Python interface. Rust spawns a persistent Python eval server and sends FEN strings over stdin. Python returns centipawn scores over stdout.

### Pros

- Much stronger engineering plan than Plan 2.
- Clear contract between the Rust engine team and the Python/Claude team.
- Testable integration point: FEN in, score out.
- Persistent process avoids subprocess-per-eval overhead.
- Sensible fallback behavior: if generated eval fails, use built-in material eval.

### Cons

- Calling Python at leaf nodes can still be slow.
- Requires disciplined integration between streams.
- The product is still mostly "play against your generated engine," which is good but could use a more memorable demo wrapper.

## LLM-PLAN4: Build Your Opponent, Refined

### Idea

This is the best version of the Build Your Opponent concept. It keeps the generated output limited to `evaluate(board)` functions and explicitly redirects impossible move-rule requests, such as "only move pawns," into position-evaluation equivalents.

### Pros

- Best technical foundation among the plans.
- Smartly avoids generating arbitrary move filters or illegal chess behavior.
- The interpretation prompt handles impossible or non-chess user requests gracefully.
- Validation gates are practical and judge-friendly:
  - Syntax
  - Safety
  - Material sanity
  - Determinism
  - Position variance
- Strong AI usage and engineering story.
- Clear parallel streams.

### Cons

- Still needs a strong demo wrapper.
- Generated eval functions may be quirky but not always strong.
- The "wow" depends on the frontend clearly showing that different philosophies produce different behavior.

## LLM-PLAN5: Chess Stakes

### Idea

Add a Kalshi/Polymarket-style prediction market layer to chess. Users watch AI philosophy showdowns, receive fake chips, and bet on outcomes such as winner, move count, or whether a sacrifice happens. Live odds update from the engine evaluation.

### Pros

- Most novel product angle.
- Live odds, fake markets, spectator rooms, and payouts create a memorable demo.
- Adds a quant/dev flavor that fits the hackathon setting.
- Strong testable modules:
  - Odds engine
  - Betting manager
  - WebSocket spectator hub
- Makes engine evaluations legible as probabilities.
- Helps turn engine behavior into an interactive social experience.

### Cons

- Real Kalshi/Polymarket integration is legally and operationally heavy.
- Lichess human-match mode adds too much scope.
- Betting can distract from the core requirement: building a chess engine.
- If framed as real-money betting, judges may focus on regulation instead of engineering.
- More backend/frontend complexity than the core engine needs.

## Recommended Unified Plan

# Chess Cubist: Build, Trade, And Battle Custom Chess Engines

The best hackathon plan is a hybrid:

- Use **LLM-PLAN4** as the core technical foundation.
- Add **LLM-PLAN1** for tournament rigor and measurable experiments.
- Add a **fake-chip-only trimmed version of LLM-PLAN5** as the demo layer.
- Borrow the spirit of **Chess Commander**, but apply natural language to engine creation rather than per-move commands.

## Core Product

Users describe a chess philosophy in natural language. Claude turns it into a validated evaluation function. That generated engine can then be:

1. Played against by the user.
2. Entered into a tournament against other generated or baseline engines.
3. Watched in a spectator room with fake prediction-market chips and live odds.

## What To Cut

To keep the project hackathon-feasible, cut or defer:

- Real Kalshi or Polymarket trading integration.
- Real-money betting.
- Lichess human match mode.
- Multiplayer matchmaking.
- Full lichess-bot deployment.
- NNUE-lite.
- Arbitrary move-rule generation.
- Per-move natural-language command interpretation.

These can remain stretch goals, but they should not be part of the core build.

## Final Architecture

```text
Chess_cubist/
├── core/                 # Rust UCI engine
│   ├── search.rs         # negamax + alpha-beta + quiescence
│   ├── eval.rs           # built-in fallback eval
│   ├── uci.rs            # UCI protocol
│   └── move_order.rs
│
├── eval/                 # Python eval generation
│   ├── eval_server.py    # persistent FEN -> score process
│   ├── generator.py      # Claude -> evaluate(board)
│   ├── validator.py      # AST safety + sanity checks
│   ├── classic.py
│   └── generated/
│
├── tournament/
│   ├── self_play.py      # generated engine vs generated engine
│   └── results/
│
├── backend/              # FastAPI
│   ├── main.py
│   ├── game_manager.py
│   ├── betting_manager.py
│   ├── odds_engine.py
│   └── spectator_hub.py
│
├── frontend/             # Next.js
│   ├── PhilosophyBuilder
│   ├── CodeViewer
│   ├── Board
│   ├── EngineInfo
│   ├── TournamentArena
│   ├── WinProbBar
│   └── BettingPanel
│
├── prompts/
│   └── eval_generator.md
│
└── tests/
```

## Demo Flow

1. A judge types: "Create an engine that loves sacrifices and hates quiet positions."
2. Claude restates it as concrete chess evaluation priorities.
3. Claude generates `evaluate(board)`.
4. The validator checks syntax, safety, determinism, material sanity, and position variance.
5. The UI shows the generated code.
6. The user plays a few moves against it.
7. The generated engine enters a mini-tournament against:
   - Materialist
   - Positional
   - Defensive
   - Another user-generated engine
8. Spectators get fake chips and bet on:
   - Match winner
   - Over/under move count
   - Whether the sacrifice engine will sacrifice material before move 20
9. Live odds update using the engine evaluation converted to win probability.
10. The README shows tournament results, prompt iterations, tests, and benchmarks.

## Why This Wins

The pitch is concise:

> We built a UCI-compatible chess engine whose evaluation function can be generated by Claude from natural language, validated for safety, benchmarked in self-play, and turned into live prediction markets around engine behavior.

This hits every judging criterion:

- **Chess quality**: Rust UCI engine, legal move generation, alpha-beta search, quiescence, perft, and Stockfish benchmark.
- **AI usage**: Claude generates eval functions, interprets philosophies, explains behavior, and is evaluated through experiments.
- **Process**: Rust core, eval generation, frontend, tournament tooling, and market systems can be built in parallel.
- **Engineering**: validation pipeline, tests, UCI, WebSockets, fake market settlement, documented prompts, and reproducible tournament results.

## Suggested Parallel Workstreams

### Stream A: Rust Engine

- Build UCI loop.
- Use a chess library such as `shakmaty` for legal move generation.
- Implement negamax, alpha-beta pruning, iterative deepening, quiescence, and move ordering.
- Add built-in fallback evaluation.
- Add `--eval-server` support for Python-generated evals.
- Add perft and search tests.

### Stream B: Claude Eval Generator

- Implement two-step interpretation and code generation prompts.
- Generate only deterministic `evaluate(board: chess.Board) -> int` functions.
- Build AST-based safety validation.
- Add sanity, determinism, and variance tests.
- Save generated evals with metadata and prompt history.

### Stream C: Tournament And Benchmarks

- Build self-play harness.
- Run baseline engines against generated engines.
- Record JSON results.
- Add Stockfish benchmark at low skill levels if available.
- Produce a simple standings table for the demo.

### Stream D: Frontend And Demo Layer

- Build the philosophy input flow.
- Show generated code.
- Show chessboard and engine info.
- Add tournament viewer.
- Add fake-chip betting panel and live win probability bar.

## Minimum Viable Demo

The core demo should include:

- Generate one custom engine from natural language.
- Validate and display its code.
- Play a legal game against it.
- Run a small tournament with at least three engines.
- Show fake-chip odds for one AI-vs-AI game.
- Display results and prompt history.

## Stretch Goals

- Claude move explanations in the generated philosophy's voice.
- Export generated personality as a standalone UCI engine.
- Shareable spectator room.
- Move-specific markets, such as "will the next move be a capture?"
- Lichess-bot deployment.
- Real public-market data display from Kalshi or Polymarket, without live trading.

## Final Recommendation

Use **LLM-PLAN4** as the technical core, add **LLM-PLAN1's tournament rigor**, and include a **fake-chip-only version of LLM-PLAN5** for the product demo.

This creates the strongest whole plan: technically credible, visibly AI-native, interactive at the engine level, and memorable enough for judges.
