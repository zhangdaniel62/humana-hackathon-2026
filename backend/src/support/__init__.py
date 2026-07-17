"""Authenticated customer-to-representative support infrastructure."""

from .registry import SupportConnection, SupportRegistry
from .store import SupportRoomConflict, SupportStore

__all__ = [
    "SupportConnection",
    "SupportRegistry",
    "SupportRoomConflict",
    "SupportStore",
]
