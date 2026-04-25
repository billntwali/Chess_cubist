"""WebSocket fan-out: broadcast one game's events to N spectators."""
from fastapi import WebSocket


class SpectatorHub:
    def __init__(self):
        # game_id -> list of connected spectator websockets
        self._rooms: dict[str, list[WebSocket]] = {}

    async def join(self, game_id: str, ws: WebSocket):
        await ws.accept()
        self._rooms.setdefault(game_id, []).append(ws)

    async def leave(self, game_id: str, ws: WebSocket):
        room = self._rooms.get(game_id, [])
        if ws in room:
            room.remove(ws)

    async def broadcast(self, game_id: str, payload: dict):
        disconnected = []
        for ws in self._rooms.get(game_id, []):
            try:
                await ws.send_json(payload)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            await self.leave(game_id, ws)
