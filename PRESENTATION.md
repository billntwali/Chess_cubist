# Chess Forge — Presentation Script
**5 minutes · ~1.5 min demo · 5 speakers**

---

## The Problem & The Idea

Chess.com has personality bots — Magnus, Hikaru, preset styles. You pick one and play. That's it. You can't invent your opponent. You can't see how it thinks. The AI is a skin on top.

We asked: what if you could *describe* any chess personality in plain English, and the engine's actual brain gets written live, on screen, in front of you?

> *"A paranoid coward that never attacks"*
> *"A suicidal gambler that sacrifices everything for an attack"*
> *"An obsessive pawn hoarder that never trades material"*

Each one becomes a different engine with different logic. You play against your own creation, watch it narrate its moves in character, and then pit it against classic grandmaster styles in a live tournament.

That's Chess Forge.

---

## How We Used Claude to Plan & Build

**Claude wasn't just a tool — it was a team member**

![How we used Claude](how_we_used_claude.png)

**Planning:**
- Fed the hackathon rubric into a `CLAUDE.md` file — Claude read the judging criteria first
- Iterated through four plan files (`LLM-PLAN1` → `PLAN4`), getting pushback, refinements, and discarded ideas each round
- Submitted all team plans; Claude compared them and picked the strongest one
- Claude wrote a five-person implementation plan — each of us selected a role, and Plan Mode generated our individual specs

**Building:**
- Every team member had their own Claude agent focused on their layer — Rust engine, eval generator, backend, frontend, tester
- Claude wrote essentially all the code
- The Rust-Python interface contract was designed in conversation with Claude and committed as a spec *before* either side was built — both streams built in parallel without stepping on each other

---

## How Claude Works Inside the Engine

**Every time you type a philosophy, this pipeline runs:**

1. **Interpret (Claude Haiku)** — Maps your description to a chess-expressible concept. "Paranoid coward" becomes: *"Maximizes king safety, penalizes open files near own king, avoids all trades."* Impossible inputs like "only move pawns" get redirected gracefully.

2. **Generate (Claude Sonnet)** — Writes a Python `evaluate(board) -> int` function from scratch, live. The code appears on screen as it generates. This function decides how the engine values every position.

3. **5-gate validation** — Before the engine touches a game: syntax, safety, sanity on canonical positions, determinism, variance. Any failure surfaces the exact error and prompts a rephrase.

4. **Rust calls Python at every node** — For each leaf node in the search tree, Rust sends a FEN to the Python eval server and gets back a centipawn score. The personality runs at the heart of every search.

5. **Narrate (Claude Haiku)** — After every engine move, Claude writes one sentence in the personality's voice: *"The Coward tucks the bishop back, unwilling to risk a single exchange."*

---

## The Engineering

- **Rust engine** — alpha-beta, iterative deepening, quiescence search, transposition table, MVV-LVA. UCI compliant — loads into any chess GUI in the world
- **Persistent eval bridge** — Rust spawns one Python process per game. FEN in, centipawn score out. No recompiling for new personalities
- **Test suite** — perft tests at depth 1–4 (including Kiwipete), mate-in-N, eval sanity, 5-gate generator tests
- **Pipeline tester** — `make agent` runs 5 automated checks end-to-end: build, eval server, generator, UCI handshake, 3 live games
- **Prompt iteration logged** — every prompt is in `prompts/` with iteration notes. The AI usage story is documented, not just claimed

---

## Demo

`make dev` → type a philosophy → Generate → Play → Tournament

**Closer:**
> *"One text box. Any chess personality you can describe. Claude writes the brain, the Rust engine plays it, and Claude narrates every move in character. That's Chess Forge."*

---

## Quick Reference — Key Numbers for Q&A

| Fact | Value |
|------|-------|
| Lines of code | ~2,000 (all Claude-written) |
| Plan iterations | 4 (LLM-PLAN1 → PLAN4) |
| Validation gates | 5 |
| Claude touchpoints per game | 3 (interpret, generate, narrate per move) |
| Tournament opponents | Tal · Karpov · Petrosian |
| Test modules | 5 (perft, eval, generator, search, tournament) |
| Languages | Rust · Python · TypeScript |
| Engine protocol | UCI (Universal Chess Interface) |
