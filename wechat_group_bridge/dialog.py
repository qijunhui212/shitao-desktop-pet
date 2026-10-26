from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QPlainTextEdit,
    QVBoxLayout,
)

from .models import BridgeSettings


class WechatBridgeDialog(QDialog):
    start_requested = Signal(object)
    stop_requested = Signal()
    view_memory_requested = Signal()

    def __init__(self, settings: BridgeSettings, parent=None):
        super().__init__(parent)
        self._settings = settings.validated()
        self._active = False
        self.setWindowTitle("师滔 · 微信群接入")
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.WindowStaysOnTopHint)
        self.setMinimumWidth(500)
        from app.dialog_theme import apply_dialog_light_theme, picker_dialog_stylesheet
        apply_dialog_light_theme(self)
        self.setStyleSheet(picker_dialog_stylesheet())
        self.setStyleSheet(self.styleSheet() + """
            QPushButton { background: #F1D995; color: #3E2B20; border: 1px solid #72501B; }
            QPushButton:hover { background: #E7CA83; color: #332219; }
            QPushButton:focus { border: 2px solid #4D3512; }
            QLineEdit { border: 1px solid #72501B; }
            QLineEdit:focus { border: 2px solid #4D3512; }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 16)
        root.setSpacing(10)
        title = QLabel("微信群接入")
        title.setObjectName("heading")
        root.addWidget(title)
        info = QLabel(
            "后台读取这个群开始监听后的新文字消息，无需讲述人或保持群窗口打开。开启群记忆后，新消息保存在本机，每小时通过当前聊天 API 整理一次；"
            "摘要可供这个群和桌宠私聊回忆。生成回复或整理时，相关消息、群名、昵称及记忆会发给该 API。没有新消息不调用整理 API。"
        )
        info.setWordWrap(True)
        root.addWidget(info)

        form = QFormLayout()
        form.setSpacing(8)
        self.group_input = QLineEdit(self._settings.group_name)
        self.group_input.setMaxLength(100)
        self.group_input.setAccessibleName("要监听的微信群名称")
        form.addRow("微信群名称", self.group_input)
        root.addLayout(form)

        self.reply_cb = QCheckBox("群成员 @ 当前微信账号时自动回复（识别实际昵称）")
        self.reply_cb.setChecked(self._settings.auto_reply_enabled)
        root.addWidget(self.reply_cb)
        self.idle_cb = QCheckBox("群内 20 分钟没有新消息时，主动发一句（每段安静期最多一次）")
        self.idle_cb.setChecked(self._settings.idle_announcement_enabled)
        root.addWidget(self.idle_cb)
        self.memory_cb = QCheckBox("每小时整理群记忆（群聊和桌宠私聊都能回忆）")
        self.memory_cb.setChecked(self._settings.hourly_memory_enabled)
        root.addWidget(self.memory_cb)
        self.memory_status = QLabel("等待接收新的群消息")
        self.memory_status.setWordWrap(True)
        self.memory_status.setAccessibleName("群记忆整理状态")
        root.addWidget(self.memory_status)
        self._status = QLabel("已停止监听")
        self._status.setObjectName("hint")
        root.addWidget(self._status)

        row = QHBoxLayout()
        self.view_memory_btn = QPushButton("查看群记忆")
        self.view_memory_btn.clicked.connect(self.view_memory_requested.emit)
        row.addWidget(self.view_memory_btn)
        row.addStretch()
        self.close_btn = QPushButton("关闭")
        self.close_btn.clicked.connect(self.accept)
        self.start_btn = QPushButton("开始监听")
        self.start_btn.setDefault(True)
        self.start_btn.clicked.connect(self._start_or_stop)
        row.addWidget(self.close_btn)
        row.addWidget(self.start_btn)
        root.addLayout(row)

        self.start_requested.connect(self._on_start_requested)
        self.stop_requested.connect(self._on_stop_requested)

    def settings(self) -> BridgeSettings:
        return BridgeSettings(
            group_name=self.group_input.text(),
            listening_enabled=self._active,
            auto_reply_enabled=self.reply_cb.isChecked(),
            idle_announcement_enabled=self.idle_cb.isChecked(),
            hourly_memory_enabled=self.memory_cb.isChecked(),
            mention_text="@师滔",
            cooldown_seconds=self._settings.cooldown_seconds,
        ).validated()

    def set_status(self, status: str) -> None:
        self._status.setText(status)

    def set_active(self, active: bool) -> None:
        self._active = active
        self.group_input.setEnabled(not active)
        self.reply_cb.setEnabled(not active)
        self.idle_cb.setEnabled(not active)
        self.memory_cb.setEnabled(not active)
        self.start_btn.setText("停止监听" if active else "开始监听")

    def _start_or_stop(self) -> None:
        if self._active:
            self.stop_requested.emit()
            return
        try:
            settings = self.settings()
        except ValueError as exc:
            self._status.setText(str(exc))
            self.group_input.setFocus()
            return
        self.start_requested.emit(settings)

    def _on_start_requested(self, _settings) -> None:
        self.set_status("正在连接微信…")

    def _on_stop_requested(self) -> None:
        self.set_status("正在停止…")

    def show_memories(self, content: str) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("师滔 · 群记忆和消息出处")
        dialog.resize(720, 540)
        layout = QVBoxLayout(dialog)
        text = QPlainTextEdit(dialog)
        from app.dialog_theme import TEXT_PRIMARY, BG_INPUT
        text.setStyleSheet(f'QPlainTextEdit {{ color: {TEXT_PRIMARY}; background: {BG_INPUT}; }}')
        text.setReadOnly(True)
        text.setPlainText(content)
        text.setAccessibleName("最近一百条群记忆与原消息出处")
        layout.addWidget(text)
        close = QPushButton("关闭", dialog)
        close.clicked.connect(dialog.accept)
        layout.addWidget(close)
        dialog.exec()
