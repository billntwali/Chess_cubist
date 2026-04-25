"""Post-move narration: Gemini describes each engine move in the philosophy's voice."""
import os
from google import genai

_client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))

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
        response = _client.models.generate_content(
            model="gemini-1.5-flash",
            contents=prompt,
        )
        return response.text.strip()

    return await asyncio.to_thread(_call)
