"""Post-move narration: LLM describes each engine move in the philosophy's voice."""
from openai import OpenAI

_client = OpenAI()

COMMENTARY_PROMPT = """\
Chess engine playing "{philosophy}" just played {san} in this position: {fen}
Engine evaluation: {cp} centipawns (positive = White better).

Write ONE vivid sentence narrating this move as if the philosophy is acting.
Do not mention centipawns or evaluation scores. Be concise and dramatic."""


async def get_commentary(philosophy: str, move_uci: str, fen: str, eval_cp: int) -> str:
    """Return a one-sentence narration of the engine's move."""
    import asyncio
    import chess

    try:
        board = chess.Board(fen)
        move = chess.Move.from_uci(move_uci)
        san = board.san(move)
    except Exception:
        san = move_uci

    prompt = COMMENTARY_PROMPT.format(
        philosophy=philosophy,
        san=san,
        fen=fen,
        cp=eval_cp,
    )

    def _call():
        msg = _client.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=128,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.choices[0].message.content.strip()

    return await asyncio.to_thread(_call)
