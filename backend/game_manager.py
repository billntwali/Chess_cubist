"""Manages active games: spawns Rust + Python eval processes per game."""
import asyncio
import subprocess
import uuid
from pathlib import Path

from fastapi import WebSocket

from backend.commentary import get_commentary
from backend.odds_engine import centipawns_to_prob
from backend.spectator_hub import SpectatorHub

RUST_BINARY = Path(__file__).parents[1] / "core" / "target" / "release" / "chess_forge"
EVAL_SERVER = Path(__file__).parents[1] / "eval" / "eval_server.py"

hub = SpectatorHub()

# game_id -> GameState
_games: dict[str, "GameState"] = {}


class GameState:
    def __init__(self, game_id: str, eval_path: str, player_ws: WebSocket):
        self.game_id = game_id
        self.eval_path = eval_path
        self.player_ws = player_ws
        self.engine_proc: subprocess.Popen | None = None
        self.fen = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
        self.moves: list[str] = []

    def start_engine(self):
        eval_cmd = f"python {EVAL_SERVER} {self.eval_path}"
        self.engine_proc = subprocess.Popen(
            [str(RUST_BINARY), "--eval-server", eval_cmd],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        self._uci_handshake()

    def _uci_handshake(self):
        self._send("uci")
        self._read_until("uciok")
        self._send("isready")
        self._read_until("readyok")

    def _send(self, cmd: str):
        self.engine_proc.stdin.write(cmd + "\n")
        self.engine_proc.stdin.flush()

    def _read_until(self, token: str) -> list[str]:
        lines = []
        while True:
            line = self.engine_proc.stdout.readline().strip()
            lines.append(line)
            if line == token:
                return lines

    def get_best_move(self, movetime_ms: int = 1000) -> tuple[str, int, str]:
        """Return (best_move_uci, eval_cp, pv)."""
        position_cmd = "position startpos"
        if self.moves:
            position_cmd += " moves " + " ".join(self.moves)
        self._send(position_cmd)
        self._send(f"go movetime {movetime_ms}")

        info_lines = self._read_until_bestmove()
        best_move = ""
        eval_cp = 0
        pv = ""

        for line in info_lines:
            if line.startswith("info") and "score cp" in line:
                parts = line.split()
                try:
                    eval_cp = int(parts[parts.index("cp") + 1])
                    if "pv" in parts:
                        pv = " ".join(parts[parts.index("pv") + 1:])
                except (ValueError, IndexError):
                    pass
            if line.startswith("bestmove"):
                best_move = line.split()[1]

        return best_move, eval_cp, pv

    def _read_until_bestmove(self) -> list[str]:
        lines = []
        while True:
            line = self.engine_proc.stdout.readline().strip()
            lines.append(line)
            if line.startswith("bestmove"):
                return lines

    def stop(self):
        if self.engine_proc:
            self._send("quit")
            self.engine_proc.wait(timeout=5)


async def start_game(eval_path: str, ws: WebSocket) -> str:
    game_id = uuid.uuid4().hex[:8]
    state = GameState(game_id, eval_path, ws)
    _games[game_id] = state
    await asyncio.to_thread(state.start_engine)
    return game_id


async def handle_move(game_id: str, move_uci: str, philosophy: str):
    state = _games[game_id]
    state.moves.append(move_uci)

    best_move, eval_cp, pv = await asyncio.to_thread(state.get_best_move)
    state.moves.append(best_move)

    white_prob = centipawns_to_prob(eval_cp)
    commentary = await get_commentary(philosophy, best_move, state.fen, eval_cp)

    payload = {
        "best_move": best_move,
        "eval_cp": eval_cp,
        "white_prob": white_prob,
        "pv": pv,
        "commentary": commentary,
    }

    await state.player_ws.send_json(payload)
    await hub.broadcast(game_id, payload)


def end_game(game_id: str):
    state = _games.pop(game_id, None)
    if state:
        state.stop()
