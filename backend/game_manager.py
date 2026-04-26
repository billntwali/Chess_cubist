"""Manages active games: spawns Rust + Python eval processes per game."""
import asyncio
import chess
import subprocess
import uuid
from pathlib import Path
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect

from backend.commentary import get_commentary
from backend.odds_engine import centipawns_to_prob
from backend.spectator_hub import SpectatorHub

RUST_BINARY = Path(__file__).parents[1] / "core" / "target" / "release" / "chess_forge"
EVAL_SERVER = Path(__file__).parents[1] / "eval" / "eval_server.py"

hub = SpectatorHub()

_games: dict[str, "GameState"] = {}
_pending: dict[str, tuple[str, str]] = {}  # game_id -> (eval_path, philosophy)


def _white_prob_from_result(result: str) -> float:
    if result == "1-0":
        return 1.0
    if result == "0-1":
        return 0.0
    return 0.5


def _eval_cp_from_result(result: str) -> int:
    if result == "1-0":
        return 900_000
    if result == "0-1":
        return -900_000
    return 0


def _board_result_payload(board: chess.Board) -> dict | None:
    """Return standardized game-over payload fields if board is terminal."""
    outcome = board.outcome(claim_draw=True)
    if outcome is None:
        return None

    result = outcome.result()
    termination = outcome.termination.name.lower()
    termination_label = termination.replace("_", " ").title()

    if outcome.winner is None:
        winner = None
        result_text = f"{termination_label} — Draw"
    else:
        winner = "white" if outcome.winner else "black"
        if termination == "checkmate":
            result_text = f"Checkmate — {winner.title()} wins"
        else:
            result_text = f"{termination_label} — {winner.title()} wins"

    return {
        "game_over": True,
        "result": result,
        "winner": winner,
        "termination": termination,
        "result_text": result_text,
    }


def _forfeit_payload(loser: str) -> dict:
    loser = loser.lower()
    winner = "black" if loser == "white" else "white"
    result = "0-1" if winner == "black" else "1-0"
    return {
        "game_over": True,
        "result": result,
        "winner": winner,
        "termination": "forfeit",
        "result_text": f"{loser.title()} resigned — {winner.title()} wins",
    }


class GameState:
    def __init__(self, game_id: str, eval_path: str, player_ws: WebSocket):
        self.game_id = game_id
        self.eval_path = eval_path
        self.player_ws = player_ws
        self.engine_proc: Optional[subprocess.Popen] = None
        self.board = chess.Board()
        self.moves: list[str] = []

    def start_engine(self):
        if not RUST_BINARY.exists():
            raise FileNotFoundError(
                f"Rust binary not found at {RUST_BINARY}. Run: make build"
            )
        import sys
        eval_cmd = f"{sys.executable} {EVAL_SERVER} {self.eval_path}"
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

    def get_best_move(self, movetime_ms: int = 500) -> tuple[str, int, str, int]:
        """Return (best_move_uci, eval_cp, pv, depth)."""
        position_cmd = "position startpos"
        if self.moves:
            position_cmd += " moves " + " ".join(self.moves)
        self._send(position_cmd)
        self._send(f"go movetime {movetime_ms} depth 4")

        best_move = ""
        eval_cp = 0
        pv = ""
        depth = 0

        while True:
            line = self.engine_proc.stdout.readline().strip()
            if line.startswith("info") and "score cp" in line:
                parts = line.split()
                try:
                    eval_cp = int(parts[parts.index("cp") + 1])
                    if "depth" in parts:
                        depth = int(parts[parts.index("depth") + 1])
                    if "pv" in parts:
                        pv = " ".join(parts[parts.index("pv") + 1:])
                except (ValueError, IndexError):
                    pass
            if line.startswith("bestmove"):
                best_move = line.split()[1]
                break

        return best_move, eval_cp, pv, depth

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
            action = data.get("action")
            if action == "forfeit":
                await handle_forfeit(game_id, loser="white")
                break

            move_uci = data.get("move")
            if move_uci:
                finished = await handle_move(game_id, move_uci, philosophy)
                if finished:
                    break
    except (WebSocketDisconnect, Exception):
        pass
    finally:
        end_game(game_id)
        try:
            await ws.close()
        except Exception:
            pass


async def handle_move(game_id: str, move_uci: str, philosophy: str):
    state = _games.get(game_id)
    if state is None:
        return False

    # Apply player's move to our board tracker
    try:
        state.board.push_uci(move_uci)
    except Exception:
        return False  # Illegal move — ignore
    state.moves.append(move_uci)

    # Player may have delivered checkmate/stalemate/etc.
    game_over = _board_result_payload(state.board)
    if game_over:
        result = game_over["result"]
        payload = {
            "fen": state.board.fen(),
            "eval_cp": _eval_cp_from_result(result),
            "white_prob": _white_prob_from_result(result),
            "pv": "",
            "depth": 0,
            **game_over,
        }
        await state.player_ws.send_json(payload)
        await hub.broadcast(game_id, payload)
        return True

    # Snapshot FEN for commentary (position the engine is responding to)
    pre_engine_fen = state.board.fen()

    # Ask the engine for its response
    best_move, eval_cp, pv, depth = await asyncio.to_thread(state.get_best_move)
    if not best_move or best_move == "0000":
        game_over = _board_result_payload(state.board)
        if game_over:
            result = game_over["result"]
            payload = {
                "fen": state.board.fen(),
                "eval_cp": _eval_cp_from_result(result),
                "white_prob": _white_prob_from_result(result),
                "pv": "",
                "depth": 0,
                **game_over,
            }
            await state.player_ws.send_json(payload)
            await hub.broadcast(game_id, payload)
            return True
        await state.player_ws.send_json({"error": "Engine returned no legal move."})
        return False

    state.moves.append(best_move)
    try:
        state.board.push_uci(best_move)
    except Exception:
        pass

    # eval_cp is from side-to-move perspective in negamax logs. Engine move was by Black,
    # so this value maps to Black's perspective at root; invert for White perspective.
    eval_cp_white = -eval_cp
    white_prob = centipawns_to_prob(eval_cp_white)
    commentary = await get_commentary(philosophy, best_move, pre_engine_fen, eval_cp)

    payload = {
        "best_move": best_move,
        "fen": state.board.fen(),
        "eval_cp": eval_cp_white,
        "white_prob": white_prob,
        "pv": pv,
        "depth": depth,
        "commentary": commentary,
    }

    game_over = _board_result_payload(state.board)
    if game_over:
        result = game_over["result"]
        payload.update(game_over)
        payload["eval_cp"] = _eval_cp_from_result(result)
        payload["white_prob"] = _white_prob_from_result(result)

    await state.player_ws.send_json(payload)
    await hub.broadcast(game_id, payload)
    return bool(game_over)


async def handle_forfeit(game_id: str, loser: str = "white"):
    state = _games.get(game_id)
    if state is None:
        return

    game_over = _forfeit_payload(loser)
    result = game_over["result"]
    payload = {
        "fen": state.board.fen(),
        "eval_cp": _eval_cp_from_result(result),
        "white_prob": _white_prob_from_result(result),
        "pv": "",
        "depth": 0,
        "commentary": game_over["result_text"],
        **game_over,
    }
    await state.player_ws.send_json(payload)
    await hub.broadcast(game_id, payload)


def end_game(game_id: str):
    state = _games.pop(game_id, None)
    if state:
        state.stop()
