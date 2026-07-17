"""FastAPI entrypoint: ADK agent endpoints plus the browser-mic voice bridge.

Run from ``backend/``::

    uv run uvicorn main:app --reload

Surface:
- ADK dev UI and REST endpoints (``/run``, ``/run_sse``, session CRUD): ``/``
- Live voice WebSocket: ``/ws/voice``
- Browser microphone demo page: ``/demo``
"""

from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

from fastapi import Depends
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from google.adk.cli.fast_api import get_fast_api_app

from src.agents import SentinelAgent
from src.api.auth import router as auth_router
from src.api.operations import router as operations_router
from src.api.voice import router as voice_router
from src.auth import AuthSettings, AuthStore, UserRole
from src.auth.dependencies import require_role
from src.auth.http import authentication_middleware
from src.auth.websocket import WebSocketRouteGuardMiddleware
from src.events import event_log
from src.models import MetricsBaseline

BACKEND_DIR = Path(__file__).resolve().parent
auth_settings = AuthSettings()

app = get_fast_api_app(
    agents_dir=str(BACKEND_DIR / "agents"),
    web=True,
    allow_origins=auth_settings.allowed_origins,
)
app.state.auth_settings = auth_settings
app.state.auth_store = AuthStore(
    auth_settings.database_path,
    session_ttl=timedelta(hours=auth_settings.session_ttl_hours),
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
    application.state.auth_store.initialize(
        enable_demo_seed=application.state.auth_settings.enable_demo_seed
    )
    await sentinel.start(replay_existing=True)
    try:
        async with _adk_lifespan(application):
            yield
    finally:
        await sentinel.stop()


app.router.lifespan_context = _claim_assist_lifespan
app.add_middleware(WebSocketRouteGuardMiddleware, state=app.state)
app.middleware("http")(authentication_middleware)
app.include_router(auth_router)
app.include_router(operations_router)
app.include_router(voice_router)


@app.get(
    "/operations",
    include_in_schema=False,
    dependencies=[Depends(require_role(UserRole.MANAGER))],
)
def operations_dashboard() -> FileResponse:
    return FileResponse(BACKEND_DIR / "static" / "operations.html")


app.mount(
    "/demo",
    StaticFiles(directory=BACKEND_DIR / "static", html=True),
    name="demo",
)
