"""FastAPI entrypoint: /api/interpret, /api/generate, /api/game/start,
/ws/game/{id}, /ws/spectate/{id}, /api/tournament."""
import asyncio
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="Chess Forge")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Eval generation
# ---------------------------------------------------------------------------

class InterpretRequest(BaseModel):
    description: str


class GenerateRequest(BaseModel):
    interpreted: str


@app.post("/api/interpret")
async def interpret_endpoint(req: InterpretRequest):
    from eval.generator import interpret
    result = await asyncio.to_thread(interpret, req.description)
    return {"interpreted": result}


@app.post("/api/generate")
async def generate_endpoint(req: GenerateRequest):
    from eval.generator import generate, validate, save_eval
    code = await asyncio.to_thread(generate, req.interpreted)
    ok, err = validate(code)
    if not ok:
        return {"ok": False, "error": err, "code": code}
    eval_path = save_eval(code, req.interpreted)
    return {"ok": True, "code": code, "eval_path": str(eval_path)}


# ---------------------------------------------------------------------------
# Game management
# ---------------------------------------------------------------------------

class StartGameRequest(BaseModel):
    eval_path: str
    philosophy: str


@app.post("/api/game/start")
async def start_game_endpoint(req: StartGameRequest):
    from backend.game_manager import reserve_game
    game_id = reserve_game(req.eval_path, req.philosophy)
    return {"game_id": game_id}


@app.websocket("/ws/game/{game_id}")
async def game_ws(websocket: WebSocket, game_id: str):
    from backend.game_manager import run_game_ws
    await run_game_ws(game_id, websocket)


@app.websocket("/ws/spectate/{game_id}")
async def spectate_ws(websocket: WebSocket, game_id: str):
    from backend.game_manager import hub
    await hub.join(game_id, websocket)
    try:
        while True:
            # Keep the connection alive; spectators only receive, never send
            await websocket.receive_text()
    except (WebSocketDisconnect, Exception):
        await hub.leave(game_id, websocket)


# ---------------------------------------------------------------------------
# Tournament (UI-friendly wrapper: accepts user eval + adds classic opponents)
# ---------------------------------------------------------------------------

class TournamentUIRequest(BaseModel):
    user_eval_path: str
    user_name: str = "You"
    games_per_pair: int = 2   # small default — full tournament via `make tournament`
    movetime_ms: int = 200
    search_depth: int = 2


@app.post("/api/tournament")
async def run_tournament_from_ui(req: TournamentUIRequest) -> dict:
    from backend.tournament_runner import run_tournament
    personalities_dir = Path(__file__).parents[1] / "eval" / "personalities"
    engines = {
        req.user_name or "You": req.user_eval_path,
        "Tal": str(personalities_dir / "tal.py"),
        "Karpov": str(personalities_dir / "karpov.py"),
        "Petrosian": str(personalities_dir / "petrosian.py"),
    }
    return await asyncio.to_thread(
        run_tournament, engines, req.games_per_pair, req.movetime_ms, req.search_depth
    )
