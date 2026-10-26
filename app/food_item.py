"""桌面上随机出现的食物，拖到宠物上喂食。"""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QPoint, Qt
from PySide6.QtWidgets import QLabel, QWidget

from pet.vitality_art import food_tooltip, make_food_pixmap


class FoodItemWindow(QWidget):
    def __init__(
        self,
        desktop_pos: QPoint,
        food_kind: int,
        *,
        pet_window: QWidget,
        on_fed: Callable[[], None],
        parent=None,
    ):
        super().__init__(parent)
        self._pet_window = pet_window
        self._on_fed = on_fed
        self._drag_offset: QPoint | None = None
        pix = make_food_pixmap(food_kind)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(pix.size())
        self.setToolTip(food_tooltip(food_kind))

        self._label = QLabel(self)
        self._label.setPixmap(pix)
        self._label.setGeometry(0, 0, pix.width(), pix.height())

        self.move(desktop_pos.x(), desktop_pos.y())
        self.show()
        self.raise_()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = None
            if self._hits_pet():
                self._on_fed()
            self.close()
        super().mouseReleaseEvent(event)

    def _hits_pet(self) -> bool:
        return self._pet_window.frameGeometry().intersects(self.frameGeometry())
