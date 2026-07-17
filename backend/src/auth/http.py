"""HTTP authentication context and coarse route protection."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse

from .models import AuthUser, UserRole

logger = logging.getLogger(__name__)

_PUBLIC_PATHS = frozenset({"/health", "/version", "/api/auth/login"})
_MANAGER_EXACT_PATHS = frozenset(
    {
        "/",
        "/docs",
        "/docs/oauth2-redirect",
        "/openapi.json",
        "/redoc",
        "/list-apps",
        "/run",
        "/run_sse",
        "/run_live",
    }
)
_MANAGER_PREFIXES = (
    "/apps/",
    "/dev-ui",
    "/dev/",
    "/builder/",
)


def _manager_only(path: str) -> bool:
    return path in _MANAGER_EXACT_PATHS or path.startswith(_MANAGER_PREFIXES)


def _response(status_code: int, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"detail": detail})


async def authentication_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    """Resolve the session cookie and fail closed outside the public allowlist."""

    settings = request.app.state.auth_settings
    store = request.app.state.auth_store
    origin = request.headers.get("origin")
    if origin and origin not in settings.allowed_origins:
        logger.info("Denied HTTP request from untrusted origin=%s", origin)
        return _response(status.HTTP_403_FORBIDDEN, "Origin not allowed")
    token = request.cookies.get(settings.cookie_name)
    user: AuthUser | None = store.resolve_session(token)
    request.state.auth_user = user
    request.state.auth_token = token

    path = request.url.path
    if request.method == "OPTIONS" or path in _PUBLIC_PATHS:
        return await call_next(request)
    if user is None:
        logger.info("Denied unauthenticated HTTP request path=%s", path)
        return _response(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    if _manager_only(path) and user.role is not UserRole.MANAGER:
        logger.info(
            "Denied manager-only HTTP request user=%s path=%s", user.username, path
        )
        return _response(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
    if (path == "/operations" or path.startswith("/operations/")) and (
        user.role is not UserRole.MANAGER
    ):
        logger.info(
            "Denied operations page user=%s role=%s", user.username, user.role.value
        )
        return _response(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
    if (path == "/demo" or path.startswith("/demo/")) and (
        user.role is not UserRole.REP
    ):
        logger.info(
            "Denied rep demo user=%s role=%s", user.username, user.role.value
        )
        return _response(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
    return await call_next(request)
