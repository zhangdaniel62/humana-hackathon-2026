"""FastAPI entrypoint: ADK agent endpoints plus the browser-mic voice bridge.

Run from ``backend/``::

    uv run uvicorn main:app --reload

Surface:
- ADK dev UI and REST endpoints (``/run``, ``/run_sse``, session CRUD): ``/``
- Live voice WebSocket: ``/ws/voice``
- Browser microphone demo page: ``/demo``
"""

from pathlib import Path

from fastapi.staticfiles import StaticFiles
from google.adk.cli.fast_api import get_fast_api_app

from src.api.voice import router as voice_router

BACKEND_DIR = Path(__file__).resolve().parent

app = get_fast_api_app(
    agents_dir=str(BACKEND_DIR / "agents"),
    web=True,
    allow_origins=["*"],
)
app.include_router(voice_router)
app.mount(
    "/demo",
    StaticFiles(directory=BACKEND_DIR / "static", html=True),
    name="demo",
)
