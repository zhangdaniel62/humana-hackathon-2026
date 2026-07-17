"""Fail-closed protection for WebSockets not owned by the conversation API."""

from __future__ import annotations

import logging
from http.cookies import SimpleCookie

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from .models import UserRole

logger = logging.getLogger(__name__)

_CONVERSATION_PATHS = frozenset({"/ws/conversation", "/ws/voice"})


def _application_owned_websocket(path: str | None) -> bool:
    return path in _CONVERSATION_PATHS or bool(
        path and path.startswith("/ws/support/")
    )


class WebSocketRouteGuardMiddleware:
    """Reserve raw ADK and unknown WebSockets for authenticated managers."""

    def __init__(self, app: ASGIApp, *, state) -> None:
        self.app = app
        self.state = state

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "websocket" or _application_owned_websocket(
            scope.get("path")
        ):
            await self.app(scope, receive, send)
            return

        headers = Headers(scope=scope)
        origin = headers.get("origin")
        settings = self.state.auth_settings
        if origin and origin not in settings.allowed_origins:
            logger.info("Denied raw WebSocket from untrusted origin=%s", origin)
            await send({"type": "websocket.close", "code": 4403})
            return

        cookies = SimpleCookie()
        cookies.load(headers.get("cookie", ""))
        morsel = cookies.get(settings.cookie_name)
        token = morsel.value if morsel is not None else None
        user = settings.bypass_user() or self.state.auth_store.resolve_session(token)
        if user is None:
            logger.info("Denied unauthenticated raw WebSocket path=%s", scope.get("path"))
            await send({"type": "websocket.close", "code": 4401})
            return
        if user.role is not UserRole.MANAGER:
            logger.info(
                "Denied raw WebSocket user=%s role=%s path=%s",
                user.username,
                user.role.value,
                scope.get("path"),
            )
            await send({"type": "websocket.close", "code": 4403})
            return

        await self.app(scope, receive, send)
