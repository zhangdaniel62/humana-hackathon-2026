"""FastAPI dependencies for authenticated users, roles, and capabilities."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status

from .models import AuthUser, Capability, UserRole


def current_user(request: Request) -> AuthUser:
    user = getattr(request.state, "auth_user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    return user


CurrentUser = Annotated[AuthUser, Depends(current_user)]


def require_role(*roles: UserRole) -> Callable[[CurrentUser], AuthUser]:
    allowed = frozenset(roles)

    def dependency(user: CurrentUser) -> AuthUser:
        if user.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return dependency

def require_capability(
    capability: Capability,
) -> Callable[[CurrentUser], AuthUser]:
    def dependency(user: CurrentUser) -> AuthUser:
        if not user.has(capability):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return dependency
