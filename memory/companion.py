"""陪伴相关 profile 读写。"""

from __future__ import annotations

from datetime import date, datetime

from memory.store import MemoryStore

KEY_LAST_OPEN = "companion_last_open_at"
KEY_LAST_CHAT = "companion_last_chat_at"
KEY_FIRST_OPEN = "companion_first_open_at"
KEY_CHAT_COUNT = "companion_chat_count"
KEY_BEHAVIOR_FIRED = "companion_behavior_fired"


class CompanionStore:
    def __init__(self, memory: MemoryStore):
        self._memory = memory

    def touch_open(self) -> float:
        """记录本次打开，返回距上次打开的间隔（小时）。"""
        now = datetime.now()
        prev_raw = self._memory.get_profile(KEY_LAST_OPEN, "")
        hours_away = 0.0
        if prev_raw:
            from brain.companion_greeting import hours_since

            hours_away = hours_since(prev_raw)
        iso = now.isoformat(timespec="seconds")
        self._memory.set_profile(KEY_LAST_OPEN, iso)
        if not self._memory.get_profile(KEY_FIRST_OPEN, ""):
            self._memory.set_profile(KEY_FIRST_OPEN, iso)
        return hours_away

    def touch_close(self) -> None:
        self._memory.set_profile(
            KEY_LAST_OPEN, datetime.now().isoformat(timespec="seconds")
        )

    def touch_chat(self) -> None:
        self._memory.set_profile(
            KEY_LAST_CHAT, datetime.now().isoformat(timespec="seconds")
        )
        try:
            n = int(self._memory.get_profile(KEY_CHAT_COUNT, "0"))
        except ValueError:
            n = 0
        self._memory.set_profile(KEY_CHAT_COUNT, str(n + 1))

    def chat_count(self) -> int:
        try:
            return int(self._memory.get_profile(KEY_CHAT_COUNT, "0"))
        except ValueError:
            return 0

    def first_open_raw(self) -> str:
        return self._memory.get_profile(KEY_FIRST_OPEN, "")

    def behaviors_fired_today(self) -> set[str]:
        import json

        raw = self._memory.get_profile(KEY_BEHAVIOR_FIRED, "")
        if not raw.strip():
            return set()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return set()
        today = date.today().isoformat()
        return {key for key, fired in data.items() if fired == today}

    def mark_behavior_fired(self, rule_key: str) -> None:
        import json

        raw = self._memory.get_profile(KEY_BEHAVIOR_FIRED, "")
        data: dict[str, str] = {}
        if raw.strip():
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                data = {}
        data[rule_key] = date.today().isoformat()
        self._memory.set_profile(KEY_BEHAVIOR_FIRED, json.dumps(data, ensure_ascii=False))
