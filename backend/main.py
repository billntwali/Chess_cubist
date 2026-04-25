"""FastAPI entrypoint: /generate, /ws/game/{id}, /ws/spectate/{id}, /tournament."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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


# Routes are registered in their respective modules; import to trigger registration.
from backend import game_manager, spectator_hub  # noqa: E402, F401
from backend.tournament_runner import router as tournament_router  # noqa: E402

app.include_router(tournament_router)
