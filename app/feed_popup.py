"""宠物头顶短暂显示喂食加血提示。"""

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QLabel, QWidget


class FeedPopupLabel(QLabel):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(11)
        font.setBold(True)
        self.setFont(font)
        self.hide()
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def show_bonus(self, text: str, *, color: QColor | None = None) -> None:
        c = color or QColor(80, 200, 90)
        self.setStyleSheet(
            f"color: rgb({c.red()},{c.green()},{c.blue()});"
            "background: rgba(0,0,0,140);"
            "border-radius: 6px;"
            "padding: 2px 8px;"
        )
        self.setText(text)
        self.adjustSize()
        self.show()
        self.raise_()
        self._hide_timer.start(1600)
