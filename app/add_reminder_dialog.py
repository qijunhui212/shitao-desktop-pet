"""Manually add a reminder without chat API."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QDateTime, Qt
from PySide6.QtWidgets import (
    QDateTimeEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from brain.tools import validate_reminder_datetime


class AddReminderDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._title = ""
        self._trigger_iso = ""

        self.setWindowTitle("添加提醒")
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setMinimumWidth(360)
        self.setStyleSheet(
            """
            QDialog { background: #FFF8F0; }
            QLineEdit, QDateTimeEdit {
                background: white; border: 1px solid #E8D5B5;
                border-radius: 6px; padding: 6px; color: #5C4033;
            }
            QPushButton {
                background: #C9A227; color: white; border: none;
                padding: 8px 16px; border-radius: 8px;
            }
            QPushButton:hover { background: #B8922A; }
            QPushButton#secondary {
                background: transparent; color: #5C4033;
                border: 1px solid #E8D5B5;
            }
            """
        )

        root = QVBoxLayout(self)
        hint = QLabel("无需聊天 API，到点会通过托盘通知提醒。")
        hint.setWordWrap(True)
        root.addWidget(hint)

        form = QFormLayout()
        self._title_edit = QLineEdit()
        self._title_edit.setPlaceholderText("例如：开会、喝水")
        form.addRow("标题", self._title_edit)
        self._when = QDateTimeEdit(QDateTime.currentDateTime().addSecs(3600))
        self._when.setCalendarPopup(True)
        self._when.setDisplayFormat("yyyy-MM-dd HH:mm")
        form.addRow("时间", self._when)
        root.addLayout(form)

        row = QHBoxLayout()
        row.addStretch()
        cancel = QPushButton("取消")
        cancel.setObjectName("secondary")
        cancel.clicked.connect(self.reject)
        ok = QPushButton("添加")
        ok.clicked.connect(self._on_ok)
        row.addWidget(cancel)
        row.addWidget(ok)
        root.addLayout(row)

    def title(self) -> str:
        return self._title

    def trigger_at(self) -> str:
        return self._trigger_iso

    def _on_ok(self) -> None:
        title = self._title_edit.text().strip()
        if not title:
            QMessageBox.warning(self, "添加提醒", "请填写提醒标题。")
            return
        qdt = self._when.dateTime()
        py_dt = qdt.toPython()
        iso = py_dt.isoformat(timespec="seconds")
        parsed = validate_reminder_datetime(iso)
        if not parsed:
            QMessageBox.warning(self, "添加提醒", "时间格式无效，请重新选择。")
            return
        if parsed <= datetime.now():
            QMessageBox.warning(self, "添加提醒", "提醒时间需要在未来。")
            return
        self._title = title
        self._trigger_iso = iso
        self.accept()
