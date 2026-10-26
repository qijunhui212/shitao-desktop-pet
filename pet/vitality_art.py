"""程序内绘制的骷髅与多种食物图标（无需外部素材）。"""

from __future__ import annotations

import random
from typing import Callable

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap, QPen

FOOD_COUNT = 5
_FOOD_NAMES = ("鱼", "肉", "饭", "果", "菜")


def _draw_fish(p: QPainter, size: int) -> None:
    p.setBrush(QColor(255, 160, 80))
    p.setPen(QPen(QColor(200, 90, 40), 2))
    p.drawEllipse(6, size // 2 - 8, size - 14, 16)
    p.drawPolygon(
        [
            QPoint(size - 8, size // 2),
            QPoint(size - 2, size // 2 - 6),
            QPoint(size - 2, size // 2 + 6),
        ]
    )
    p.setBrush(QColor(255, 255, 255))
    p.drawEllipse(12, size // 2 - 2, 5, 5)


def _draw_meat(p: QPainter, size: int) -> None:
    p.setBrush(QColor(180, 70, 70))
    p.setPen(QPen(QColor(120, 40, 40), 2))
    p.drawRoundedRect(8, 10, size - 16, size - 14, 8, 8)
    p.setBrush(QColor(255, 200, 200))
    p.drawEllipse(size // 2 - 4, size // 2, 8, 6)


def _draw_rice(p: QPainter, size: int) -> None:
    p.setBrush(QColor(240, 235, 220))
    p.setPen(QPen(QColor(160, 150, 130), 2))
    p.drawEllipse(4, 14, size - 8, size - 18)
    p.setPen(QPen(QColor(80, 80, 80), 1))
    for i in range(5):
        p.drawPoint(size // 2 - 8 + i * 4, 18 + (i % 2) * 2)


def _draw_fruit(p: QPainter, size: int) -> None:
    p.setBrush(QColor(220, 60, 60))
    p.setPen(QPen(QColor(140, 30, 30), 2))
    p.drawEllipse(8, 12, size - 16, size - 16)
    p.setBrush(QColor(60, 140, 50))
    p.drawEllipse(size // 2 - 4, 6, 10, 8)


def _draw_veggie(p: QPainter, size: int) -> None:
    p.setBrush(QColor(90, 180, 70))
    p.setPen(QPen(QColor(50, 120, 40), 2))
    p.drawEllipse(10, 8, size - 20, size - 12)
    p.setBrush(QColor(120, 200, 90))
    p.drawEllipse(6, 14, 14, 10)
    p.drawEllipse(size - 22, 16, 12, 12)


_FOOD_DRAWERS: tuple[Callable[[QPainter, int], None], ...] = (
    _draw_fish,
    _draw_meat,
    _draw_rice,
    _draw_fruit,
    _draw_veggie,
)


def make_food_pixmap(kind: int | None = None, size: int = 44) -> QPixmap:
    """kind 0..4；None 则随机一种。"""
    if kind is None:
        kind = random.randint(0, FOOD_COUNT - 1)
    kind = int(kind) % FOOD_COUNT
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    _FOOD_DRAWERS[kind](p, size)
    p.end()
    return pix


def random_food_kind() -> int:
    return random.randint(0, FOOD_COUNT - 1)


def food_tooltip(kind: int) -> str:
    return f"{_FOOD_NAMES[kind % FOOD_COUNT]} · 拖到宠物身上喂食"


def make_skeleton_pixmap(width: int, height: int) -> QPixmap:
    pix = QPixmap(max(48, width), max(64, height))
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    cx, cy = pix.width() // 2, pix.height() // 2
    scale = min(pix.width(), pix.height()) / 120.0
    p.translate(cx, cy)
    p.scale(scale, scale)

    bone = QColor(220, 220, 225)
    dark = QColor(80, 80, 90)
    p.setPen(QPen(dark, 3))
    p.setBrush(bone)

    p.drawEllipse(-28, -42, 56, 50)
    p.setBrush(dark)
    p.drawEllipse(-16, -32, 12, 16)
    p.drawEllipse(4, -32, 12, 16)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawArc(-10, -18, 20, 12, 0, -180 * 16)

    for i in range(-2, 3):
        p.drawLine(-18 + i * 4, 8, -18 + i * 4, 36)
    p.drawLine(-22, 10, 22, 10)
    p.drawLine(-30, 12, -48, 28)
    p.drawLine(30, 12, 48, 28)

    p.end()
    return pix
