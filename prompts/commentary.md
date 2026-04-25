# Commentary Prompt

Used in `backend/commentary.py`. Generates one-sentence post-move narration per engine move.

**Model:** `claude-haiku-4-5` (fast, async — must not block the game loop)

---

## Prompt

```
Chess engine playing "{philosophy}" just played {san} in this position: {fen}
Engine evaluation: {cp} centipawns (positive = White better).

Write ONE vivid sentence narrating this move as if the philosophy is acting.
Do not mention centipawns or evaluation scores. Be concise and dramatic.
```

---

## Example outputs

| Philosophy | Move | Commentary |
|-----------|------|-----------|
| "suicidal attacker" | Nf5 | "The attacker lunges forward, leaving the bishop hanging — the king is the only prize worth chasing." |
| "paranoid defender" | Ke2 | "The king retreats deeper into the fortress, refusing to leave anything to chance." |
| "pawn hoarder" | exd5 | "Another pawn claimed — the collection grows, indifferent to what must be sacrificed in return." |

---

## Iteration notes

| Version | Change | Reason |
|---------|--------|--------|
| v1 | Initial prompt | — |
