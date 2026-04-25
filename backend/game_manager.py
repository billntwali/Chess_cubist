"""Manages active games: spawns Rust + Python eval processes per game."""
import asyncio
import chess
import subprocess
import uuid
from pathlib import Path

from fastapi import WebSocket, WebSocketDisconnect

from backend.commentary import get_commentary
from backend.odds_engine import centipawns_to_prob
from backend.spectator_hub import SpectatorHub

RUST_BINARY = Path(__file__).parents[1] / "core" / "target" / "release" / "chess_forge"
EVAL_SERVER = Path(__file__).parents[1] / "eval" / "eval_server.py"

hub = SpectatorHub()

_games: dict[str, "GameState"] = {}
_pending: dict[str, tuple[str, str]] = {}  # game_id -> (eval_path, philosophy)


class GameState:
    def __init__(self, game_id: str, eval_path: str, player_ws: WebSocket):
        self.game_id = game_id
        self.eval_path = eval_path
        self.player_ws = player_ws
        self.engine_proc: subprocess.Popen | None = None
        self.board = chess.Board()
        self.moves: list[str] = []

    def start_engine(self):
        if not RUST_BINARY.exists():
            raise FileNotFoundError(
                f"Rust binary not found at {RUST_BINARY}. Run: make build"
            )
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

        best_move = ""
        eval_cp = 0
        pv = ""

        while True:
            line = self.engine_proc.stdout.readline().strip()
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
                break

        return best_move, eval_cp, pv

    def stop(self):
        if self.engine_proc:
            try:
                self._send("quit")
                self.engine_proc.wait(timeout=5)
            except Exception:
                self.engine_proc.kill()


def reserve_game(eval_path: str, philosophy: str) -> str:
    """Register a pending game and return the game_id. Engine starts on WS connect."""
    game_id = uuid.uuid4().hex[:8]
    _pending[game_id] = (eval_path, philosophy)
    return game_id


async def run_game_ws(game_id: str, ws: WebSocket):
    """Accept a player WebSocket, start the engine, and handle the move loop."""
    config = _pending.pop(game_id, None)
    if config is None:
        await ws.close(code=4404)
        return
    eval_path, philosophy = config

    await ws.accept()
    state = GameState(game_id, eval_path, ws)
    _games[game_id] = state

    try:
        await asyncio.to_thread(state.start_engine)
    except Exception as e:
        await ws.send_json({"error": str(e)})
        await ws.close()
        _games.pop(game_id, None)
        return

    try:
        while True:
            data = await ws.receive_json()
            move_uci = data.get("move")
            if move_uci:
                await handle_move(game_id, move_uci, philosophy)
    except (WebSocketDisconnect, Exception):
        end_game(game_id)


async def handle_move(game_id: str, move_uci: str, philosophy: str):
    state = _games.get(game_id)
    if state is None:
        return

    # Apply player's move to our board tracker
    try:
        state.board.push_uci(move_uci)
    except Exception:
        return  # Illegal move — ignore
    state.moves.append(move_uci)

    # Snapshot FEN for commentary (position the engine is responding to)
    pre_engine_fen = state.board.fen()

    # Ask the engine for its response
    best_move, eval_cp, pv = await asyncio.to_thread(state.get_best_move)
    if not best_move or best_move == "0000":
        return

    state.moves.append(best_move)
    try:
        state.board.push_uci(best_move)
    except Exception:
        pass

    white_prob = centipawns_to_prob(eval_cp)
    commentary = await get_commentary(philosophy, best_move, pre_engine_fen, eval_cp)

    payload = {
        "best_move": best_move,
        "fen": state.board.fen(),
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
