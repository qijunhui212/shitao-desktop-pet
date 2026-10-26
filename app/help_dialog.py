"""Scrollable help / about dialogs."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
)


class TextHelpDialog(QDialog):
    def __init__(self, title: str, body: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setMinimumSize(420, 360)
        self.setStyleSheet(
            """
            QDialog { background: #FFF8F0; }
            QLabel { color: #5C4033; font-size: 12px; }
            QScrollArea { border: 1px solid #E8D5B5; border-radius: 8px; background: white; }
            QPushButton {
                background: #C9A227; color: white; border: none;
                padding: 8px 20px; border-radius: 8px;
            }
            QPushButton:hover { background: #B8922A; }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        label = QLabel(body)
        label.setWordWrap(True)
        label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        scroll.setWidget(label)
        root.addWidget(scroll, stretch=1)

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        root.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)


def show_help_dialog(title: str, body: str, parent=None) -> None:
    TextHelpDialog(title, body, parent).exec()
