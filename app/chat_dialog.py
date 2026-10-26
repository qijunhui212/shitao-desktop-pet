"""Independent input composer; pet replies go to its head bubble."""
from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtGui import QKeyEvent, QFont, QPalette, QPixmap, QPainter
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit, QVBoxLayout, QCheckBox, QLineEdit

class MessageInput(QPlainTextEdit):
    submit = Signal()
    def keyPressEvent(self, event: QKeyEvent):
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and not event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            self.submit.emit()
            event.accept()
            return
        super().keyPressEvent(event)

class ChatDialog(QDialog):
    user_name_changed = Signal(str)
    message_sent = Signal(str)
    stop_requested = Signal()
    import_memory_requested = Signal()
    save_memory_requested = Signal()
    manage_memory_requested = Signal()
    sticker_settings_changed = Signal(object)
    reply_text = Signal(str)
    reply_chunk = Signal(str)
    reply_started = Signal()
    reply_finished = Signal()
    def __init__(self, pet_name: str, parent=None):
        super().__init__(parent)
        self.setFont(QFont('Microsoft YaHei UI',10))
        from config.paths import resolve_resource_path
        from app.chat_theme import apply_theme
        self._backdrop=QPixmap(str(resolve_resource_path('assets/ui/chat-background.png')))
        apply_theme(self)
        self._pet_name, self._busy = pet_name, False
        self._last_sent, self._error_text, self._waiting_seconds = '', '', 0
        self._waiting_timer=QTimer(self)
        self._waiting_timer.timeout.connect(self._update_waiting)
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint)
        self.setMinimumSize(540, 450)
        self.resize(570, 510)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(26,24,26,22)
        layout.setSpacing(13)
        title=QLabel('和师滔说说话')
        title.setObjectName('composerTitle')
        layout.addWidget(title)
        self._hint = QLabel('回复显示在桌宠头顶 · Enter 发送，Shift+Enter 换行')
        self._hint.setWordWrap(True)
        layout.addWidget(self._hint)
        name_row = QHBoxLayout()
        name_row.addWidget(QLabel('你的称呼'))
        self.name_input = QLineEdit()
        self.name_input.setMaxLength(24)
        self.name_input.setAccessibleName('使用者称呼')
        self.name_input.setPlaceholderText('首次聊天前填写，例如小王')
        self._confirmed_name = ''
        name_row.addWidget(self.name_input,1)
        name_save = QPushButton('保存称呼')
        name_save.clicked.connect(self._save_name)
        name_row.addWidget(name_save)
        layout.addLayout(name_row)
        self.input = MessageInput()
        self.input.setMinimumHeight(115)
        palette=self.input.palette()
        palette.setColor(QPalette.ColorRole.PlaceholderText,palette.color(QPalette.ColorRole.Text))
        self.input.setPalette(palette)
        self.input.setPlaceholderText('跟他说点什么…')
        self.input.setAccessibleName('给桌宠的消息')
        self.input.submit.connect(self._send)
        layout.addWidget(self.input)
        memory_row = QHBoxLayout()
        self._save_memory_btn = QPushButton('存为记忆')
        self._save_memory_btn.setToolTip('使用选中文字、输入框内容或最近聊天，确认后存入知识库')
        self._save_memory_btn.clicked.connect(self.save_memory_requested.emit)
        memory_row.addWidget(self._save_memory_btn)
        self._manage_memory_btn = QPushButton('管理新增记忆')
        self._manage_memory_btn.clicked.connect(self.manage_memory_requested.emit)
        memory_row.addWidget(self._manage_memory_btn)
        memory_row.addStretch()
        layout.addLayout(memory_row)
        from brain.stickers import settings
        options = settings()
        sticker_row = QHBoxLayout()
        self.chat_stickers = QCheckBox('聊天配表情')
        self.idle_stickers = QCheckBox('闲置动作配表情')
        self.chat_stickers.setChecked(options['chat'])
        self.idle_stickers.setChecked(options['idle'])
        for control in (self.chat_stickers, self.idle_stickers):
            sticker_row.addWidget(control)
            control.toggled.connect(lambda _checked: self.sticker_settings_changed.emit({'chat': self.chat_stickers.isChecked(), 'idle': self.idle_stickers.isChecked()}))
        layout.addLayout(sticker_row)
        speech_row=QHBoxLayout()
        self.proactive = QCheckBox('偶尔主动提问')
        self.monologue = QCheckBox('偶尔自言自语')
        self.proactive.setToolTip('闲置检查时5%概率；与自言自语共用10分钟冷却；本地运行，不调用API')
        self.monologue.setToolTip('闲置检查时3%概率；至少间隔20分钟；本地运行，不调用API')
        for control,key in ((self.proactive,'proactive'),(self.monologue,'monologue')):
            control.setChecked(options.get(key,True));speech_row.addWidget(control)
        layout.addLayout(speech_row)
        for control in (self.chat_stickers,self.idle_stickers):
            control.toggled.disconnect()
        for control in (self.chat_stickers,self.idle_stickers,self.proactive,self.monologue):
            control.toggled.connect(lambda _checked:self.sticker_settings_changed.emit({'chat':self.chat_stickers.isChecked(),'idle':self.idle_stickers.isChecked(),'proactive':self.proactive.isChecked(),'monologue':self.monologue.isChecked()}))
        row = QHBoxLayout()
        self._status = QLabel('就绪')
        row.addWidget(self._status, 1)
        self._memory_btn = QPushButton('导入记忆')
        self._memory_btn.setToolTip('导入 memory.json；聊天时会发送少量相关记忆到所配置的 API')
        self._memory_btn.clicked.connect(self.import_memory_requested.emit)
        row.addWidget(self._memory_btn)
        self._stop_btn = QPushButton('停止')
        self._stop_btn.clicked.connect(self.stop_requested.emit)
        self._stop_btn.hide()
        row.addWidget(self._stop_btn)
        self._send_btn = QPushButton('发送')
        self._send_btn.setObjectName('sendPrimary')
        self._send_btn.setMinimumWidth(94)
        self._send_btn.clicked.connect(self._send)
        row.addWidget(self._send_btn)
        layout.addLayout(row)
        self.set_pet_name(pet_name)
    def paintEvent(self,event):
        super().paintEvent(event)
        if not self._backdrop.isNull() and not getattr(self,'_high_contrast',False):
            p=QPainter(self)
            p.drawPixmap(self.rect(),self._backdrop)
            p.end()
    def set_user_name(self, name):
        self._confirmed_name = name
        self.name_input.setText(name)
    def _save_name(self):
        from brain.user_identity import clean_name
        try:
            name = clean_name(self.name_input.text())
        except ValueError as exc:
            self._status.setText(str(exc));self.name_input.setFocus();return False
        self.user_name_changed.emit(name)
        return self._confirmed_name == name
    def showEvent(self, event):
        super().showEvent(event)
        (self.input if self._confirmed_name else self.name_input).setFocus()
    def set_pet_name(self, name):
        self._pet_name = name
        self.setWindowTitle(f'给{name}发消息')
    def set_busy(self, busy):
        self._busy = busy
        self._send_btn.setEnabled(not busy)
        self._stop_btn.setVisible(busy)
        if busy:
            self._error_text=''
            self._waiting_seconds=0
            self._waiting_timer.start(1000)
            self._status.setText('正在回复…')
        else:
            self._waiting_timer.stop()
            self._status.setText(self._error_text or '就绪')
    def _update_waiting(self):
        self._waiting_seconds+=1
        self._status.setText(f'等待回复 {self._waiting_seconds} 秒 · 可停止')
    def mark_failed(self):
        self._error_text='未完成 · 可重新发送'
        if not self.input.toPlainText().strip():
            self.input.setPlainText(self._last_sent)
    def _send(self):
        if self._busy:
            return
        if not self._confirmed_name or self.name_input.text().strip()!=self._confirmed_name:
            if not self._save_name():return
        text = self.input.toPlainText().strip()
        if text:
            self._last_sent=text
            self.input.clear()
            self.message_sent.emit(text)
    def append_pet(self, text):
        self.reply_text.emit(text)
    def append_pet_stream(self, text):
        self.reply_chunk.emit(text)
    def start_pet_reply(self):
        self.reply_started.emit()
    def finish_pet_reply(self):
        self.reply_finished.emit()
