# Chess Forge — Presentation Script
**5 minutes total · ~1.5 min demo · 5 speakers**

---

## Person 1 — The Problem & The Idea (~1 min)

**Why we built this**

Chess.com has personality bots — Magnus, Hikaru, preset styles. You pick one and play. That's it. You can't invent your opponent. You can't see how it thinks. The AI is a skin on top.

We asked: what if you could *describe* any chess personality in plain English, and the engine's actual brain gets written live, on screen, in front of you?

> *"A paranoid coward that never attacks"*
> *"A suicidal gambler that sacrifices everything for an attack"*
> *"An obsessive pawn hoarder that never trades material"*

Each one becomes a different engine with different logic. You play against your own creation, watch it narrate its moves in character, and then pit it against classic grandmaster styles in a live tournament.

That's Chess Forge.

---

## Person 2 — How We Used Claude to Plan & Build (~1 min)

**Claude wasn't just a tool — it was a team member**

![How we used Claude](how_we_used_claude.png)

**Planning:**
- We fed the hackathon rubric into a `CLAUDE.md` file — Claude read the judging criteria first
- Iterated through four plan files (`LLM-PLAN1` → `PLAN4`), getting pushback, refinements, and discarded ideas each round
- Submitted all team plans; Claude compared them and picked the strongest one
- Claude wrote a five-person implementation plan — each of us selected a role, and Plan Mode generated our individual specs

**Building:**
- Every team member had their own Claude agent focused on their layer — Rust engine, eval generator, backend, frontend, tester
- Claude wrote essentially all the code
- The Rust-Python interface contract was designed in conversation with Claude and committed as a spec *before* either side was built — so both streams could build in parallel without stepping on each other

---

## Person 3 — How Claude Works Inside the Engine (~1 min)

**Every time you type a philosophy, this pipeline runs:**

1. **Interpret (Claude Haiku)** — Maps your description to a chess-expressible concept. "Paranoid coward" becomes: *"Maximizes king safety and pawn structure integrity, penalizes open files near own king, avoids piece trades at all costs."* Impossible inputs like "only move pawns" get redirected gracefully.

2. **Generate (Claude Sonnet)** — Writes a Python `evaluate(board) -> int` function from scratch, live. The code appears on screen as it generates. This function is what decides how the engine values every position.

3. **5-gate validation** — Before the engine ever touches a game, the code passes: syntax check, safety check (no `os`, `subprocess`, `exec`), sanity check on canonical positions, determinism check, variance check across 10 diverse positions. Any failure surfaces the exact error and prompts a rephrase.

4. **Rust calls Python at every node** — The Rust search engine evaluates hundreds of positions per move. For each leaf node, it sends a FEN string to the Python eval server over stdin/stdout and gets back a centipawn score. The personality runs at the heart of every search.

5. **Narrate (Claude Haiku)** — After every engine move, Claude writes one sentence in the personality's voice: *"The Coward tucks the bishop back, unwilling to risk a single exchange."*

---

## Person 4 — The Engineering (~45 sec)

**Built to be real, not just a demo**

- **Rust engine** — alpha-beta search, iterative deepening, quiescence search, transposition table, MVV-LVA move ordering. UCI compliant — loads into any chess GUI in the world
- **Persistent eval bridge** — Rust spawns one Python process per game. FEN in, centipawn score out. Clean interface, no recompiling for new personalities
- **Test suite** — perft tests validate move generation against known node counts at depth 1–4 (including Kiwipete), mate-in-N tests, eval sanity tests, 5-gate generator tests
- **Pipeline tester** — `make agent` runs 5 automated checks end-to-end in ~3 minutes: build, eval server, generator, UCI handshake, 3 live games
- **Tournament** — round-robin harness saves W/D/L to JSON, renders as a bar chart in the UI
- **Prompt iteration logged** — every prompt we used is in `prompts/` with iteration notes, so the AI usage story is documented, not just claimed

---

## Person 5 — The Demo (~1.5 min)

**[Live demo — walk through this exactly]**

1. Open the app (`make dev`)
2. Type: **"a bloodthirsty attacker that sacrifices pawns to open files"**
3. Click **Generate** — show the interpreted description appearing, then the Python code generating live in the sidebar
4. Click **Play** — make 2-3 moves, show:
   - The engine responding with aggressive moves
   - The win probability bar shifting
   - Commentary appearing: *"The Gambler lunges the knight forward, ignoring the pawn it left hanging — the king is the only prize worth chasing."*
5. Click **Run Tournament** — show the bar chart populating with results vs. Tal, Karpov, Petrosian

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
