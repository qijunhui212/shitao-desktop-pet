"""在桌面可用区域内随机生成坐标（避开宠物窗口）。"""

from __future__ import annotations

import random

from PySide6.QtCore import QPoint, QRect
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QWidget


def _screen_rect() -> QRect:
    screen = QGuiApplication.primaryScreen()
    if screen:
        return screen.availableGeometry()
    return QRect(0, 0, 1920, 1080)


def random_desktop_position(
    item_w: int,
    item_h: int,
    *,
    avoid: QWidget | None = None,
    margin: int = 48,
    max_tries: int = 24,
) -> QPoint:
    """在桌面随机一点放置食物，尽量不压在宠物上。"""
    area = _screen_rect()
    left = area.left() + margin
    top = area.top() + margin
    right = area.right() - item_w - margin
    bottom = area.bottom() - item_h - margin
    if right <= left:
        left, right = area.left(), max(area.left(), area.right() - item_w)
    if bottom <= top:
        top, bottom = area.top(), max(area.top(), area.bottom() - item_h)

    avoid_rect = avoid.frameGeometry() if avoid else QRect()
    pad = 32
    if avoid_rect.isValid():
        avoid_rect = avoid_rect.adjusted(-pad, -pad, pad, pad)

    for _ in range(max_tries):
        x = random.randint(left, right) if right > left else left
        y = random.randint(top, bottom) if bottom > top else top
        candidate = QRect(x, y, item_w, item_h)
        if not avoid_rect.isValid() or not candidate.intersects(avoid_rect):
            return QPoint(x, y)

    return QPoint(
        random.randint(left, right) if right > left else left,
        random.randint(top, bottom) if bottom > top else top,
    )
