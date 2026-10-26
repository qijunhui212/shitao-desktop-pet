"""HP = 剩余存活小时（满 12）。默认仅运行时衰减；生存记忆模式关闭程序也计时。"""



from __future__ import annotations



import math

import os

from datetime import datetime



from PySide6.QtCore import QObject, QTimer, Signal



from config.pet_mode import is_survival_memory_mode, is_survival_mode

from memory.store import MemoryStore



HP_MAX = float(os.getenv("VITALITY_HP_MAX", "12"))

HP_START = float(os.getenv("VITALITY_HP_START", "6"))

FEED_HOURS = float(os.getenv("VITALITY_FEED_HOURS", "1"))

REVIVE_FEEDS = int(os.getenv("VITALITY_REVIVE_FEEDS", "3"))

REVIVE_HP = float(os.getenv("VITALITY_REVIVE_HP", "3"))

TICK_MS = int(os.getenv("VITALITY_TICK_MS", "1000"))

# 满 HP 跑完 12 小时耗尽：每秒扣 HP_MAX / (HP_MAX * 3600)

DECAY_PER_SEC = HP_MAX / (HP_MAX * 3600.0)

PROFILE_LAST_TS = "vitality_last_ts"





class PetVitality(QObject):

    hp_changed = Signal(float, float, bool)  # hp, max, starved

    starved_changed = Signal(bool)

    feed_progress = Signal(int, int)  # current feeds toward revive, needed



    def __init__(self, memory: MemoryStore, parent=None, *, enabled: bool | None = None):

        super().__init__(parent)

        self._memory = memory

        self._enabled = is_survival_mode() if enabled is None else enabled

        self._hp = HP_START

        self._starved = False

        self._revive_feeds = 0

        self._timer = QTimer(self)

        self._timer.setInterval(max(200, TICK_MS))

        self._timer.timeout.connect(self._on_tick)

        if not self._enabled:

            return

        self._load()

        self._emit_all()

        if not self._starved:

            self._timer.start()



    @property

    def enabled(self) -> bool:

        return self._enabled



    @property

    def hp(self) -> float:

        return self._hp



    @property

    def hp_max(self) -> float:

        return HP_MAX



    @property

    def is_starved(self) -> bool:

        return self._starved



    @property

    def revive_feeds(self) -> int:

        return self._revive_feeds



    def stop(self) -> None:

        if not self._enabled:

            return

        self._timer.stop()

        self._touch_timestamp()

        self._save()



    def reload_state(self) -> None:

        """设置变更后重新加载 HP（含离线结算）。"""

        if not self._enabled:

            return

        self._timer.stop()

        self._load()

        self._emit_all()

        if not self._starved:

            self._timer.start()

        else:

            self._timer.stop()



    def _load(self) -> None:

        if not self._enabled:

            return

        raw = self._memory.get_profile("vitality_hp", "")

        if raw:

            try:

                self._hp = float(raw)

            except ValueError:

                self._hp = HP_START

        else:

            self._hp = HP_START

        self._starved = self._memory.get_profile("vitality_starved", "") == "1"

        try:

            self._revive_feeds = int(self._memory.get_profile("vitality_revive_feeds", "0"))

        except ValueError:

            self._revive_feeds = 0

        if self._starved:

            self._hp = 0.0

        else:

            self._hp = max(0.0, min(HP_MAX, self._hp))

            self._apply_offline_decay()

        self._touch_timestamp()



    def _apply_offline_decay(self) -> None:

        if not is_survival_memory_mode() or self._starved:

            return

        raw_ts = self._memory.get_profile(PROFILE_LAST_TS, "").strip()

        if not raw_ts:

            return

        try:

            last = datetime.fromisoformat(raw_ts)

        except ValueError:

            return

        now = datetime.now()

        if now <= last:

            return

        elapsed_hours = (now - last).total_seconds() / 3600.0

        if elapsed_hours <= 0:

            return

        self._hp = max(0.0, self._hp - elapsed_hours)

        if self._hp <= 0.0:

            self._starved = True

            self._hp = 0.0

            self._revive_feeds = 0



    def _touch_timestamp(self) -> None:

        if not self._enabled:

            return

        self._memory.set_profile(PROFILE_LAST_TS, datetime.now().isoformat(timespec="seconds"))



    def _save(self) -> None:

        self._memory.set_profile("vitality_hp", f"{self._hp:.4f}")

        self._memory.set_profile("vitality_starved", "1" if self._starved else "0")

        self._memory.set_profile("vitality_revive_feeds", str(self._revive_feeds))



    def _emit_all(self) -> None:

        self.hp_changed.emit(self._hp, HP_MAX, self._starved)

        self.starved_changed.emit(self._starved)

        if self._starved:

            self.feed_progress.emit(self._revive_feeds, REVIVE_FEEDS)



    def _on_tick(self) -> None:

        if not self._enabled or self._starved:

            return

        self._hp = max(0.0, self._hp - DECAY_PER_SEC * (self._timer.interval() / 1000.0))

        if self._hp <= 0.0:

            self._enter_starved()

        else:

            self._touch_timestamp()

            self._save()

            self.hp_changed.emit(self._hp, HP_MAX, self._starved)



    def _enter_starved(self) -> None:

        self._hp = 0.0

        self._starved = True

        self._revive_feeds = 0

        self._timer.stop()

        self._touch_timestamp()

        self._save()

        self.starved_changed.emit(True)

        self.hp_changed.emit(0.0, HP_MAX, True)

        self.feed_progress.emit(0, REVIVE_FEEDS)



    def advance_hours(self, hours: float = 1.0) -> tuple[bool, str, float]:

        """快进时间：扣除对应 HP（加速一小时 = -1 HP）。"""

        if not self._enabled:

            return False, "当前为普通模式", 0.0

        if self._starved:

            return False, "已饿死，请先拖食物喂食复活", 0.0

        hours = max(0.0, hours)

        before = self._hp

        self._hp = max(0.0, self._hp - hours)

        delta = self._hp - before

        if self._hp <= 0.0:

            self._enter_starved()

        else:

            self._touch_timestamp()

            self._save()

            self.hp_changed.emit(self._hp, HP_MAX, False)

        return True, "加速 1 小时", delta



    def try_feed(self) -> tuple[bool, str, float]:

        """喂一次食物。返回 (成功, 提示文案, 本次增加的 HP，用于头顶飘字)。"""

        if not self._enabled:

            return False, "当前为普通模式", 0.0

        if self._starved:

            self._revive_feeds += 1

            self._touch_timestamp()

            self._save()

            self.feed_progress.emit(self._revive_feeds, REVIVE_FEEDS)

            if self._revive_feeds < REVIVE_FEEDS:

                left = REVIVE_FEEDS - self._revive_feeds

                return True, f"喂食 {self._revive_feeds}/{REVIVE_FEEDS}，再喂 {left} 次可复活", 0.0

            self._starved = False

            self._revive_feeds = 0

            self._hp = min(HP_MAX, REVIVE_HP)

            self._touch_timestamp()

            self._save()

            self._timer.start()

            self.starved_changed.emit(False)

            self.hp_changed.emit(self._hp, HP_MAX, False)

            return True, "复活啦！", REVIVE_HP



        before = self._hp

        self._hp = min(HP_MAX, self._hp + FEED_HOURS)

        delta = self._hp - before

        self._touch_timestamp()

        self._save()

        self.hp_changed.emit(self._hp, HP_MAX, False)

        return True, "喂食成功", delta



    def hp_label(self) -> str:

        if not self._enabled:

            return ""

        if self._starved:

            return f"饿死 · 喂食 {self._revive_feeds}/{REVIVE_FEEDS} 复活"

        filled = min(int(HP_MAX), max(0, math.ceil(self._hp - 1e-6)))

        suffix = " · 记忆" if is_survival_memory_mode() else ""

        return f"HP {filled}/{int(HP_MAX)}{suffix}"


