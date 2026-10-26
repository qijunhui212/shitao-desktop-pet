"""12 段 HP 条：按当前 HP 档位整段同色（1–3 全红、4–6 全黄、7–12 全绿）。"""

from __future__ import annotations

import math
import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

HP_SEGMENTS = int(os.getenv("VITALITY_HP_SEGMENTS", "12"))

_COLOR_RED = QColor(os.getenv("VITALITY_COLOR_RED", "#DC4641"))
_COLOR_YELLOW = QColor(os.getenv("VITALITY_COLOR_YELLOW", "#E6BE37"))
_COLOR_GREEN = QColor(os.getenv("VITALITY_COLOR_GREEN", "#5ABE55"))
_COLOR_EMPTY = QColor(os.getenv("VITALITY_COLOR_EMPTY", "#3A3A3A"))
_COLOR_STARVED = QColor(os.getenv("VITALITY_COLOR_STARVED", "#505050"))


def hp_tier_color(hp: float) -> QColor:
    """按当前 HP（向上取整段数）决定整条条目颜色，与已点亮段数无关。"""
    tier = min(HP_SEGMENTS, max(0, math.ceil(hp - 1e-6)))
    if tier <= 0:
        return _COLOR_EMPTY
    if tier <= 3:
        return _COLOR_RED
    if tier <= 6:
        return _COLOR_YELLOW
    return _COLOR_GREEN


def _hp_tier_color(hp: float, *, starved: bool) -> QColor:
    if starved:
        return _COLOR_STARVED
    return hp_tier_color(hp)


class HpBarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._hp = 6.0
        self._hp_max = float(HP_SEGMENTS)
        self._starved = False
        self._visible = True
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setFixedHeight(16)

    def set_survival_visible(self, visible: bool) -> None:
        self._visible = visible
        self.setVisible(visible)
        if not visible:
            self.setFixedHeight(0)
        else:
            self.setFixedHeight(16)
        self.update()

    def set_hp(self, hp: float, hp_max: float, starved: bool = False) -> None:
        self._hp = hp
        self._hp_max = max(1.0, hp_max)
        self._starved = starved
        self.update()
        self.repaint()

    def paintEvent(self, event):
        if not self._visible:
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()
        margin = 2
        inner_w = w - margin * 2
        inner_h = h - margin * 2
        n = HP_SEGMENTS
        gap = max(1, inner_w // 80)
        seg_w = max(2, (inner_w - gap * (n - 1)) // n)
        y0 = margin + 1

        p.setPen(QPen(QColor(50, 45, 40, 160), 1))
        p.setBrush(QColor(25, 25, 25, 90))
        p.drawRoundedRect(margin, margin, inner_w, inner_h, 4, 4)

        filled = 0 if self._starved else min(n, max(0, math.ceil(self._hp - 1e-6)))
        filled_color = hp_tier_color(self._hp) if filled > 0 else _COLOR_EMPTY

        for i in range(n):
            idx = i + 1
            x = margin + 1 + i * (seg_w + gap)
            if self._starved:
                fill = _COLOR_STARVED
            elif idx <= filled:
                fill = filled_color
            else:
                fill = _COLOR_EMPTY
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(fill)
            p.drawRoundedRect(x, y0, seg_w, inner_h - 2, 2, 2)
