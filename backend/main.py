"""FastAPI entrypoint: ADK agent endpoints plus the browser-mic voice bridge.

Run from ``backend/``::

    uv run uvicorn main:app --reload

Surface:
- ADK dev UI and REST endpoints (``/run``, ``/run_sse``, session CRUD): ``/``
- Live voice WebSocket: ``/ws/voice``
- Browser microphone demo page: ``/demo``
"""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from google.adk.cli.fast_api import get_fast_api_app

from src.agents import SentinelAgent
from src.api.operations import router as operations_router
from src.api.voice import router as voice_router
from src.events import event_log
from src.models import MetricsBaseline

BACKEND_DIR = Path(__file__).resolve().parent

app = get_fast_api_app(
    agents_dir=str(BACKEND_DIR / "agents"),
    web=True,
    allow_origins=["*"],
)
sentinel = SentinelAgent(
    event_log,
    baseline=MetricsBaseline(
        aht_minutes=8.5,
        fcr_rate=0.72,
        repeat_contact_rate=0.18,
        source_note="Labeled synthetic hackathon comparison assumptions",
    ),
)
app.state.event_log = event_log
app.state.sentinel = sentinel


_adk_lifespan = app.router.lifespan_context


@asynccontextmanager
async def _claim_assist_lifespan(application):
    await sentinel.start(replay_existing=True)
    try:
        async with _adk_lifespan(application):
            yield
    finally:
        await sentinel.stop()


app.router.lifespan_context = _claim_assist_lifespan
app.include_router(operations_router)
app.include_router(voice_router)


@app.get("/operations", include_in_schema=False)
def operations_dashboard() -> FileResponse:
    return FileResponse(BACKEND_DIR / "static" / "operations.html")


app.mount(
    "/demo",
    StaticFiles(directory=BACKEND_DIR / "static", html=True),
    name="demo",
)
