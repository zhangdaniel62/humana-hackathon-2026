"""Public authentication models and the role/capability matrix."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserRole(StrEnum):
    MANAGER = "manager"
    CUSTOMER = "customer"
    REP = "rep"


class Capability(StrEnum):
    MANAGER_DASHBOARD = "manager_dashboard"
    CHAT = "chat"
    REP_QUEUE = "rep_queue"
    VOICE = "voice"


ROLE_CAPABILITIES: dict[UserRole, tuple[Capability, ...]] = {
    UserRole.MANAGER: (Capability.MANAGER_DASHBOARD,),
    UserRole.CUSTOMER: (Capability.CHAT, Capability.VOICE),
    UserRole.REP: (Capability.REP_QUEUE, Capability.CHAT, Capability.VOICE),
}


def normalize_username(value: str) -> str:
    return value.strip().casefold()


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=128)
    password: str = Field(min_length=1, max_length=1024)

    @field_validator("username")
    @classmethod
    def normalized_username(cls, value: str) -> str:
        normalized = normalize_username(value)
        if not normalized:
            raise ValueError("username must not be blank")
        return normalized


class AuthUser(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: int
    username: str
    role: UserRole
    capabilities: tuple[Capability, ...]

    @classmethod
    def from_record(cls, *, user_id: int, username: str, role: str) -> "AuthUser":
        typed_role = UserRole(role)
        return cls(
            id=user_id,
            username=username,
            role=typed_role,
            capabilities=ROLE_CAPABILITIES[typed_role],
        )

    def has(self, capability: Capability) -> bool:
        return capability in self.capabilities


class LoginResponse(BaseModel):
    user: AuthUser
