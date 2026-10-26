"""本地陪伴问候与形象包 greetings.txt。"""

from __future__ import annotations

import random
from datetime import datetime
from pathlib import Path

from brain.persona_behavior import (
    pick_idle_behavior,
    pick_scheduled_behavior,
    pick_startup_behavior,
)
from config.character_config import resolve_character_dir

GREETING_FILENAMES = ("greetings.txt", "问候.txt", "开场.txt")

_DEFAULT_FIRST = (
    "嗨，我在这儿陪你～双击我可以聊天。",
    "今天也要加油呀，需要聊聊就叫我。",
    "终于见到你啦，想说什么都可以。",
)

_DEFAULT_RETURN = (
    "你回来啦，我一直在呢。",
    "好久不见～想我了吗？",
    "欢迎回来，今天过得怎么样？",
)

_DEFAULT_LONG_AWAY = (
    "好久没见你了，有点想你……",
    "终于等到你，我还以为把我忘了呢。",
    "你不在的这段时间，我一直在这等你。",
)

_DEFAULT_IDLE = (
    "在忙吗？需要陪聊就双击我～",
    "伸个懒腰……你那边还好吗？",
    "随便聊聊？我在这儿呢。",
    "要是累了，跟我说说话吧。",
)


def load_pack_greeting_lines(pack_dir: Path | None = None) -> list[str]:
    root = pack_dir if pack_dir is not None else resolve_character_dir()
    if not root or not root.is_dir():
        return []
    for name in GREETING_FILENAMES:
        path = root / name
        if not path.is_file():
            continue
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            continue
        lines = [
            line.strip()
            for line in raw.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        if lines:
            return lines
    return []


def _pick(pool: tuple[str, ...], extra: list[str]) -> str:
    choices = list(pool) + extra
    return random.choice(choices)


def _name_prefix(user_name: str) -> str:
    return f"{user_name}，" if user_name else ""


def resolve_startup_greeting(
    *,
    hours_away: float,
    user_name: str = "",
    pet_name: str = "",
    memories: list[str] | None = None,
    fired_today: set[str] | None = None,
) -> tuple[str, str | None]:
    """优先人设 [行为] 段，否则回退默认问候。返回 (台词, rule_key)。"""
    behavior_text, rule_key = pick_startup_behavior(
        hours_away=hours_away,
        user_name=user_name,
        fired_today=fired_today,
    )
    if behavior_text:
        return behavior_text, rule_key
    return (
        startup_greeting_text(
            hours_away=hours_away,
            user_name=user_name,
            pet_name=pet_name,
            memories=memories,
        ),
        None,
    )


def resolve_idle_greeting(*, user_name: str = "") -> str:
    behavior_text = pick_idle_behavior(user_name=user_name)
    if behavior_text:
        return behavior_text
    return idle_bubble_text(user_name=user_name)


def resolve_scheduled_greeting(
    *,
    user_name: str = "",
    fired_today: set[str] | None = None,
) -> tuple[str | None, str | None]:
    return pick_scheduled_behavior(user_name=user_name, fired_today=fired_today)


def startup_greeting_text(
    *,
    hours_away: float,
    user_name: str = "",
    pet_name: str = "",
    memories: list[str] | None = None,
) -> str:
    pack_lines = load_pack_greeting_lines()
    prefix = _name_prefix(user_name)
    if hours_away >= 24:
        base = _pick(_DEFAULT_LONG_AWAY, pack_lines)
    elif hours_away >= 1:
        base = _pick(_DEFAULT_RETURN, pack_lines)
    else:
        base = _pick(_DEFAULT_FIRST, pack_lines)
    text = prefix + base
    if memories and hours_away >= 1:
        snippet = memories[-1]
        if len(snippet) > 36:
            snippet = snippet[:36] + "…"
        text += f"（我还记得：{snippet}）"
    if pet_name and random.random() < 0.35:
        text = text.replace("我", pet_name, 1) if pet_name not in text else text
    return text


def idle_bubble_text(*, user_name: str = "") -> str:
    pack_lines = load_pack_greeting_lines()
    base = _pick(_DEFAULT_IDLE, pack_lines)
    return _name_prefix(user_name) + base


def parse_profile_timestamp(raw: str) -> datetime | None:
    if not raw.strip():
        return None
    try:
        return datetime.fromisoformat(raw.strip())
    except ValueError:
        return None


def hours_since(raw: str) -> float:
    dt = parse_profile_timestamp(raw)
    if not dt:
        return 0.0
    delta = datetime.now() - dt
    return max(0.0, delta.total_seconds() / 3600.0)


def companion_days_label(first_open_raw: str) -> str:
    dt = parse_profile_timestamp(first_open_raw)
    if not dt:
        return ""
    days = max(1, (datetime.now().date() - dt.date()).days + 1)
    return f"已陪伴 {days} 天"
