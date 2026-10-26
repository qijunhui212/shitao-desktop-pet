"""Opt-in bridge between the Shitao desktop pet and one Windows WeChat group."""

from .models import BridgeSettings, IncomingGroupMessage
from .policy import MessageGate, strip_pet_mention

__all__ = [
    "BridgeSettings",
    "IncomingGroupMessage",
    "MessageGate",
    "strip_pet_mention",
]
