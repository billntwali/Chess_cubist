# Chess Engine Hackathon — MEGA PLAN: "Project Chimera"

## The Elevator Pitch

To win a quant dev hackathon, an entry must maximize all four judging criteria: **Creativity, Rigor, AI Usage, and Engineering**. 

Project Chimera is an adaptive "Chameleon Engine" that perfectly satisfies the rubric by completely separating the engine logic from its personality evaluation. 
Rather than hardcoding an evaluation function, the fast Rust engine relies *entirely* on dynamic JSON parameters. This enables two distinct workflows that secure the win:
1. **The Offshore Rigor:** Creating an automated pipeline that uses Claude to generate 100+ wild personalities (e.g. "Pawn Hoarder", "Kamikaze"), hosts massive round-robin tournaments to pit them against each other, and charts cost-efficiency and ELO. *(Maxes out AI Usage & Engineering Rigor)*.
2. **The Live Demo:** Providing a web interface where a judge can physically type a natural-language philosophy, dynamically generate a safe JSON opponent profile using Claude, and play against it live. *(Maxes out Creativity)*.

---

## The Three-Pillar Architecture

### Pillar 1: The Core (Rust & engineering Rigor)
Instead of arbitrary dynamic code execution, the Rust engine is built for pure speed. The standard Negamax/Alpha-Beta search algorithms are implemented alongside a Transposition Table. 
However, **all evaluation heuristics** (Piece values, Piece-Square tables, mobility bonuses, king safety penalties) are loaded from a JSON configuration via custom UCI commands. 
* *Why it scores points:* Fast, memory-safe, deeply complex C/Rust engineering that never crashes when the AI changes paths. 

### Pillar 2: The Dojo (AI Pitting & Experiments)
A batch Python pipeline. 
* Claude is prompted: *"Generate a JSON output for a chess engine that values outposts heavily but despises castling."* 
* Dozens of these profiles are generated. 
* A massive, concurrent Python process (`python-chess`) matches them up in 100-game round-robin tournaments. 
* *Why it scores points:* Explicitly fulfills the *"Did you run experiments / pit AI generated engines against each other?"* criterion. Generates impressive graphs/tables for the `README.md` to show data-driven results.

### Pillar 3: The Arena (Creativity & Interface)
The live Next.js + FastAPI web wrapper for the final presentation.
* The judge opens the interface and types a text prompt: *"Create a chess opponent that hallucinates and loves knights."*
* Claude translates this to the JSON schema.
* The web backend hot-loads this JSON into the running Rust engine.
* The judge drags-and-drops pieces to play a standard game against their bespoke creation.
* *Bonus (Trash Talk Mode):* After every move, the engine uses Claude to explain *why* it made that move based on its current personality. 
* *Why it scores points:* Huge "wow" factor. Demonstrates how AI bridges natural language to algorithmic parameterization. 

---

## Parallel Process & Task Distribution (Team of 4)

Because the architecture relies on JSON boundaries, streams will **never block each other**.

### Stream A: Core Engineering (2 Devs - Rust)
- **Phase 1:** Build the UCI shell using `shakmaty` and `vampirc-uci`.
- **Phase 2:** Implement Alpha-Beta search, IDDFS, Quiescence, and MVV-LVA move ordering.
- **Phase 3:** Parameterize `eval.rs`. Instead of `const PAWN_VALUE: i32 = 100`, read from a dynamic `EvalConfig` struct updated via UCI.
- **Deliverable:** A compiled standard binary `chimera.exe` that listens for JSON strings over STDIN.

### Stream B: The Dojo & AI Experiments (1 Dev - Python)
- **Phase 1:** Write the `llm_translator.py` wrapper that enforces strict JSON schema output from the Claude API. 
- **Phase 2:** Write `tournament.py` automating matches between different valid JSON profiles. 
- **Phase 3:** Run the batch experiments overnight, graph the results (ELO vs Model Prompting Cost), and embed the findings directly into the documentation. 
- **Deliverable:** The data and charts proving rigorous AI experimentation. 

### Stream C: The Arena Frontend (1 Dev - TS/Web)
- **Phase 1:** Build a FastAPI endpoint to connect a websocket to the Rust binary. 
- **Phase 2:** Build the React UI featuring `react-chessboard` and the prompt input box. 
- **Phase 3:** Integrate the "Trash Talk" side-panel, passing engine PVs to Claude for live commentary.
- **Deliverable:** The interactive, "Wow"-factor web application.

---

## Testing Strategy & Deliverables

| Test / Deliverable | Purpose | Rubric Link |
|--------------------|---------|-------------|
| **README.md Graphs** | Show the win/loss matrix of 10 different generated personalities. | *AI Usage (Experiments)* |
| **Prompt Logs** | Document every iteration of the system prompt used to map text to JSON. | *Engineering (Docs)* |
| **JSON Schema Tests** | `pytest` verifying Claude cannot output invalid evaluation weights that crash the Rust engine. | *Engineering (Testing)* |
| **Perft Depth Validation** | Rust tests ensuring move generation correctness. | *Chess Quality* |
| **API Cost Analysis** | A small markdown section breaking down token usage per tournament to prove efficiency awareness. | *AI Usage (Efficiency)* |

---

## Fallback Plan

- If the Next.js frontend is impossible to finish in time, fallback to a terminal UI (Rich/Textual) where users can still "Build Their Opponent" live. 
- If the Rust engine runs behind, Stream B can plug the dynamic JSON parameters into `python-chess`'s slow baseline evaluator—ensuring the AI experiment pipeline and tournament data is still delivered for judging.
