"""设置页：当前形象摘要与打开切换/导入弹窗。"""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.dialog_theme import apply_content_light_theme


class CharacterManagePanel(QWidget):
    switch_dialog_requested = Signal()
    import_dialog_requested = Signal()

    def __init__(
        self,
        *,
        current_pack: str = "",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._current_pack = current_pack.strip()
        apply_content_light_theme(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self._current_lbl = QLabel()
        self._current_lbl.setObjectName("hint")
        self._current_lbl.setWordWrap(True)
        layout.addWidget(self._current_lbl)

        btn_row = QHBoxLayout()
        self._switch_btn = QPushButton("切换形象…")
        self._switch_btn.clicked.connect(self.switch_dialog_requested.emit)
        self._import_btn = QPushButton("导入形象…")
        self._import_btn.clicked.connect(self.import_dialog_requested.emit)
        btn_row.addWidget(self._switch_btn)
        btn_row.addWidget(self._import_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.refresh(current_pack)

    def refresh(self, current_pack: str = "") -> None:
        self._current_pack = current_pack.strip()
        if self._current_pack:
            self._current_lbl.setText(f"当前形象：{self._current_pack}")
        else:
            self._current_lbl.setText("当前尚未选择形象，请切换或导入。")
