"""AI 陪伴：问候、气泡、记忆上下文配置。"""

from __future__ import annotations

import os


def _flag(name: str, default: str = "1") -> bool:
    return os.getenv(name, default).strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def companion_enabled() -> bool:
    """总开关：问候、气泡、人设 [行为]、API 久别问候。"""
    if os.getenv("COMPANION") is not None:
        return _flag("COMPANION", "1")
    return (
        _flag("COMPANION_BUBBLES", "1")
        or _flag("COMPANION_STARTUP_GREETING", "1")
        or _flag("COMPANION_API_GREETING", "1")
        or _flag("COMPANION_BEHAVIOR", "1")
    )


def companion_bubbles_enabled() -> bool:
    return companion_enabled()


def companion_startup_greeting_enabled() -> bool:
    return companion_enabled()


def companion_api_greeting_enabled() -> bool:
    return companion_enabled()


def companion_behavior_enabled() -> bool:
    return companion_enabled()


def companion_bubble_interval_ms() -> int:
    try:
        minutes = int(os.getenv("COMPANION_BUBBLE_MINUTES", "30"))
    except ValueError:
        minutes = 30
    return max(5, minutes) * 60 * 1000


def companion_api_greeting_min_hours() -> float:
    try:
        return max(1.0, float(os.getenv("COMPANION_API_GREETING_HOURS", "6")))
    except ValueError:
        return 6.0


def memory_recent_limit() -> int:
    try:
        return max(1, int(os.getenv("MEMORY_RECENT_LIMIT", "15")))
    except ValueError:
        return 15


def chat_context_limit() -> int:
    try:
        return max(2, int(os.getenv("CHAT_CONTEXT_LIMIT", "20")))
    except ValueError:
        return 20


def chat_history_keep() -> int:
    try:
        return max(20, int(os.getenv("CHAT_HISTORY_KEEP", "80")))
    except ValueError:
        return 80


def companion_to_env(*, enabled: bool) -> dict[str, str]:
    value = "1" if enabled else "0"
    return {
        "COMPANION": value,
        "COMPANION_BUBBLES": value,
        "COMPANION_STARTUP_GREETING": value,
        "COMPANION_API_GREETING": value,
        "COMPANION_BEHAVIOR": value,
    }
