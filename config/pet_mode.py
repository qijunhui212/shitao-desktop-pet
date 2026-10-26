"""宠物运行模式：生存（扣 HP / 喂食）或普通（仅陪伴）。"""

from __future__ import annotations

import os

# survival | normal（也接受 生存 / 普通）
PET_MODE = os.getenv("PET_MODE", "survival").strip().lower()


def is_survival_mode_value(value: str) -> bool:
    v = value.strip().lower()
    if v in ("normal", "普通", "off", "0", "false", "no"):
        return False
    if v in ("survival", "生存", "on", "1", "true", "yes"):
        return True
    return v != "normal"


def is_survival_mode() -> bool:
    return is_survival_mode_value(PET_MODE)


def pet_mode_env_value(*, survival: bool) -> str:
    return "survival" if survival else "normal"


def is_survival_memory_mode_value(value: str) -> bool:
    v = value.strip().lower()
    return v in ("1", "true", "yes", "on", "survival_memory", "memory")


def is_survival_memory_mode() -> bool:
    """开启后退出程序期间仍按真实时间扣 HP（可饿死）。"""
    return is_survival_memory_mode_value(
        os.getenv("SURVIVAL_MEMORY_MODE", "0")
    )


def survival_memory_env_value(*, enabled: bool) -> str:
    return "1" if enabled else "0"


def mode_display_name() -> str:
    if not is_survival_mode():
        return "普通模式"
    if is_survival_memory_mode():
        return "生存模式 · 记忆"
    return "生存模式"
