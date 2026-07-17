"""Cookie-based login, session inspection, and logout endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request, Response, status
from fastapi.exceptions import HTTPException

from ..auth.dependencies import CurrentUser
from ..auth.models import AuthUser, LoginRequest, LoginResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _start_session(
    user: AuthUser, request: Request, response: Response
) -> LoginResponse:
    store = request.app.state.auth_store
    settings = request.app.state.auth_settings
    token = store.create_session(user)
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        max_age=settings.session_ttl_hours * 60 * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return LoginResponse(user=user)


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, response: Response) -> LoginResponse:
    store = request.app.state.auth_store
    user = store.authenticate(payload.username, payload.password)
    if user is None:
        logger.warning("Authentication failed username=%s", payload.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    logger.info("Authentication succeeded user=%s role=%s", user.username, user.role)
    return _start_session(user, request, response)


@router.post("/member-demo", response_model=LoginResponse)
def member_demo(request: Request, response: Response) -> LoginResponse:
    """Start a synthetic member session without collecting credentials."""

    settings = request.app.state.auth_settings
    if not settings.enable_demo_seed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member demo access is unavailable",
        )

    user = request.app.state.auth_store.get_active_user("customer")
    if user is None:
        logger.error("Member demo access requested without an active customer seed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Member demo access is unavailable",
        )

    logger.info("Member demo session started")
    return _start_session(user, request, response)


@router.get("/me", response_model=LoginResponse)
def me(user: CurrentUser, response: Response) -> LoginResponse:
    response.headers["Cache-Control"] = "no-store"
    return LoginResponse(user=user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(user: CurrentUser, request: Request, response: Response) -> None:
    settings = request.app.state.auth_settings
    request.app.state.auth_store.revoke_session(request.state.auth_token)
    response.delete_cookie(
        key=settings.cookie_name,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite="lax",
    )
    response.headers["Cache-Control"] = "no-store"
    logger.info("Logged out user=%s", user.username)
