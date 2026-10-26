"""Manage pending reminders — view, add, and cancel."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)


class RemindersDialog(QDialog):
    def __init__(
        self,
        reminders: list[dict],
        on_cancel: Callable[[int], bool],
        on_add: Callable[[], list[dict] | None] | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self._reminders = list(reminders)
        self._on_cancel = on_cancel
        self._on_add = on_add

        self.setWindowTitle("待办提醒")
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setMinimumSize(380, 300)
        self.setStyleSheet(
            """
            QDialog { background: #FFF8F0; }
            QListWidget {
                background: white;
                border: 1px solid #E8D5B5;
                border-radius: 8px;
                font-size: 13px;
                color: #5C4033;
            }
            QListWidget::item:selected { background: #F5E6C8; }
            QLabel#heading { font-size: 14px; font-weight: bold; color: #5C4033; }
            QPushButton {
                background: #C9A227; color: white; border: none;
                padding: 8px 16px; border-radius: 8px;
            }
            QPushButton:hover { background: #B8922A; }
            QPushButton#secondary {
                background: transparent; color: #5C4033;
                border: 1px solid #E8D5B5;
            }
            QPushButton#secondary:hover { background: #F5E6C8; }
            QPushButton#danger { background: #B85C5C; }
            QPushButton#danger:hover { background: #A04A4A; }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        heading = QLabel("待执行的提醒")
        heading.setObjectName("heading")
        layout.addWidget(heading)

        self._list = QListWidget()
        layout.addWidget(self._list, stretch=1)
        self._reload_list()

        row = QHBoxLayout()
        if on_add is not None:
            add_btn = QPushButton("添加提醒")
            add_btn.clicked.connect(self._add_reminder)
            row.addWidget(add_btn)
        cancel_btn = QPushButton("取消选中")
        cancel_btn.setObjectName("danger")
        cancel_btn.clicked.connect(self._cancel_selected)
        row.addWidget(cancel_btn)
        row.addStretch()
        close_btn = QPushButton("关闭")
        close_btn.setObjectName("secondary")
        close_btn.clicked.connect(self.accept)
        row.addWidget(close_btn)
        layout.addLayout(row)

    def _reload_list(self) -> None:
        self._list.clear()
        for r in self._reminders:
            item = QListWidgetItem(
                f"#{r['id']}  {r['title']}\n    {r['trigger_at']}"
            )
            item.setData(Qt.ItemDataRole.UserRole, r["id"])
            self._list.addItem(item)
        if self._reminders:
            self._list.setCurrentRow(0)

    def _add_reminder(self) -> None:
        if self._on_add is None:
            return
        updated = self._on_add()
        if updated is not None:
            self._reminders = updated
            self._reload_list()

    def _cancel_selected(self) -> None:
        item = self._list.currentItem()
        if not item:
            QMessageBox.information(self, "提醒", "请先选中一条提醒。")
            return
        rid = item.data(Qt.ItemDataRole.UserRole)
        title = item.text().split("\n", 1)[0]
        ok = QMessageBox.question(
            self,
            "取消提醒",
            f"确定取消 {title} 吗？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ok != QMessageBox.StandardButton.Yes:
            return
        if self._on_cancel(rid):
            row = self._list.currentRow()
            self._list.takeItem(row)
            self._reminders = [r for r in self._reminders if r["id"] != rid]
            if self._list.count() == 0:
                QMessageBox.information(self, "提醒", "已无待办提醒。")
        else:
            QMessageBox.warning(self, "提醒", "取消失败，请重试。")
