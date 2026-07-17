"""FastAPI entrypoint: ADK agent endpoints plus the browser-mic voice bridge.

Run from ``backend/``::

    uv run uvicorn main:app --reload

Surface:
- ADK dev UI and REST endpoints (``/run``, ``/run_sse``, session CRUD): ``/``
- Live voice WebSocket: ``/ws/voice``
- Browser microphone demo page: ``/demo``
"""

import logging
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
from src.api.prevention import router as prevention_router
from src.api.support import router as support_router
from src.api.voice import router as voice_router
from src.auth import AuthSettings, AuthStore, UserRole
from src.auth.dependencies import require_role
from src.auth.http import authentication_middleware
from src.auth.websocket import WebSocketRouteGuardMiddleware
from src.events import SQLiteEventStore, event_log
from src.clients.claims import CsvClaimsRepository
from src.delegation import DelegationTraceStore
from src.models import MetricsBaseline
from src.operations import OperationsStore
from src.prevention import PreventionScanner, PreventionStore
from src.support import SupportRegistry, SupportStore

BACKEND_DIR = Path(__file__).resolve().parent
logger = logging.getLogger(__name__)
auth_settings = AuthSettings()
if auth_settings.bypass_enabled:
    logger.warning(
        "AUTH BYPASS ENABLED: all requests use the synthetic %s identity",
        auth_settings.bypass_role.value,
    )

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
metrics_baseline = MetricsBaseline(
    aht_minutes=8.5,
    fcr_rate=0.72,
    repeat_contact_rate=0.18,
    source_note="Labeled synthetic hackathon comparison assumptions",
)
sentinel = SentinelAgent(event_log, baseline=metrics_baseline)
app.state.event_log = event_log
app.state.event_store = SQLiteEventStore(auth_settings.database_path)
app.state.sentinel = sentinel
app.state.operations_store = OperationsStore(
    auth_settings.database_path,
    BACKEND_DIR.parent / "datasets",
    baseline=metrics_baseline,
)
app.state.prevention_store = PreventionStore(auth_settings.database_path)
app.state.prevention_scanner = PreventionScanner(
    CsvClaimsRepository(), app.state.prevention_store
)
app.state.delegation_trace_store = DelegationTraceStore(
    auth_settings.database_path
)
app.state.support_store = SupportStore(auth_settings.database_path)
app.state.support_registry = SupportRegistry()


_adk_lifespan = app.router.lifespan_context


@asynccontextmanager
async def _claim_assist_lifespan(application):
    application.state.auth_store.initialize(
        enable_demo_seed=application.state.auth_settings.enable_demo_seed
    )
    application.state.operations_store = OperationsStore(
        application.state.auth_store.database_path,
        BACKEND_DIR.parent / "datasets",
        baseline=metrics_baseline,
    )
    application.state.operations_store.initialize(
        enable_demo_seed=application.state.auth_settings.enable_demo_seed
    )
    application.state.prevention_store = PreventionStore(
        application.state.auth_store.database_path
    )
    application.state.prevention_store.initialize()
    application.state.prevention_scanner = PreventionScanner(
        CsvClaimsRepository(), application.state.prevention_store
    )
    application.state.delegation_trace_store = DelegationTraceStore(
        application.state.auth_store.database_path
    )
    application.state.delegation_trace_store.initialize()
    application.state.event_store = SQLiteEventStore(
        application.state.auth_store.database_path
    )
    application.state.event_store.initialize()
    application.state.support_store = SupportStore(
        application.state.auth_store.database_path
    )
    application.state.support_store.initialize()
    application.state.support_registry = SupportRegistry()
    event_log.attach_store(application.state.event_store, replay=True)
    try:
        application.state.prevention_scanner.scan(
            idempotency_key="startup-actionable-v1",
            source="startup",
        )
    except Exception:
        # The conversation and existing operational surfaces remain usable if
        # an external population source is unavailable. Readiness reports the
        # last completed scan rather than pretending the scan succeeded.
        logger.exception("The idempotent startup prevention scan failed")
    await sentinel.start(replay_existing=True)
    try:
        async with _adk_lifespan(application):
            yield
    finally:
        await sentinel.stop()
        event_log.detach_store()


app.router.lifespan_context = _claim_assist_lifespan
app.add_middleware(WebSocketRouteGuardMiddleware, state=app.state)
app.middleware("http")(authentication_middleware)
app.include_router(auth_router)
app.include_router(operations_router)
app.include_router(prevention_router)
app.include_router(support_router)
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
