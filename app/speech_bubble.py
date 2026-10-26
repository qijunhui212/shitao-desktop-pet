"""Non-activating, screen-clamped reply bubble anchored above the pet."""
from PySide6.QtCore import QEvent, QPointF, Qt, QTimer, QRectF
from PySide6.QtGui import QPainter, QPainterPath, QPalette, QPen, QFont, QPixmap
from PySide6.QtWidgets import QApplication, QPlainTextEdit, QVBoxLayout, QWidget, QLabel

from brain import stickers
from config.paths import resolve_resource_path

class SpeechBubbleLabel(QWidget):
    def __init__(self, pet):
        super().__init__(pet, Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                         Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self._pet, self._raw, self._streaming = pet, '', False
        self._tail_x = 150
        self._sticker_id = None
        self._user_context = ""
        self._stickers_enabled = True
        self._last_sticker_id = None
        self._last_sticker_time = 0
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setWindowTitle('桌宠头顶消息')
        self.resize(300, 110)
        self.editor = QPlainTextEdit(self)
        self.editor.setFont(QFont('Microsoft YaHei UI',10))
        self.editor.setReadOnly(True)
        self.editor.setFrameStyle(0)
        self.editor.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.editor.setAccessibleName('桌宠回复')
        self.editor.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.editor.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 23)
        layout.setSpacing(6)
        layout.addWidget(self.editor)
        self.sticker_image = QLabel(self)
        self.sticker_image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sticker_image.hide()
        layout.addWidget(self.sticker_image)
        self.sticker_caption = QLabel(self)
        self.sticker_caption.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sticker_caption.setWordWrap(True)
        self.sticker_caption.hide()
        layout.addWidget(self.sticker_caption)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)
        pet.installEventFilter(self)
        self.hide()
    def eventFilter(self, watched, event):
        if watched is self._pet:
            if event.type() in (QEvent.Type.Move, QEvent.Type.Resize, QEvent.Type.Show):
                self.reposition()
            elif event.type() in (QEvent.Type.Hide, QEvent.Type.Close):
                self.hide()
        return super().eventFilter(watched, event)
    def reposition(self):
        center = self._pet.frameGeometry().center()
        screen = QApplication.screenAt(center) or QApplication.primaryScreen()
        area = screen.availableGeometry()
        self.setFixedWidth(min(300, area.width()-16))
        x = max(area.left()+8, min(center.x()-self.width()//2, area.right()-self.width()-8))
        y = max(area.top()+8, self._pet.frameGeometry().top()-self.height()-2)
        self.move(x, y)
        self._tail_x = max(24, min(self.width()-24, center.x()-x))
        self.update()
    def paintEvent(self, event):
        # Native palette follows OS light/dark and high-contrast settings.
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(1, 1, self.width()-2, self.height()-15), 12, 12)
        tail = QPainterPath(QPointF(self._tail_x-9, self.height()-15))
        tail.lineTo(self._tail_x, self.height()-2)
        tail.lineTo(self._tail_x+9, self.height()-15)
        tail.closeSubpath()
        path = path.united(tail)
        p.setPen(QPen(self.palette().color(QPalette.ColorRole.Text), 1.5))
        p.setBrush(self.palette().color(QPalette.ColorRole.Base))
        p.drawPath(path)
    def _render(self):
        text, proposed = stickers.extract(self._raw, self._streaming)
        if self._streaming and proposed is not None:
            self._set_sticker(stickers.choose(self._user_context, text, proposed))
        for marker in ('REMINDER_JSON:', 'MEMORY_JSON:'):
            text = text.split(marker, 1)[0]
        lines = text.splitlines()
        if lines and len(lines[-1]) >= 3 and any(m.startswith(lines[-1]) for m in ('REMINDER_JSON:', 'MEMORY_JSON:')):
            lines.pop()
        text = chr(10).join(lines).strip() or ('正在回复…' if self._streaming else '这次没有收到回复，请重新发送。')
        self.editor.setPlainText(text)
        count = max(1, sum(max(1,(len(line)+17)//18) for line in text.splitlines()))
        extra = 215 if self._sticker_id else 0
        text_height = min(140 if extra else 196, max(40, count*22))
        screen = QApplication.screenAt(self._pet.frameGeometry().center()) or QApplication.primaryScreen()
        self.editor.setFixedHeight(text_height)
        self.setFixedHeight(min(screen.availableGeometry().height()-16, 33+text_height+extra))
        bar = self.editor.verticalScrollBar()
        bar.setValue(bar.maximum())
        self.reposition()
        self.show()
        self.raise_()
    def start_reply(self):
        self._raw, self._streaming = '', True
        self._set_sticker(None)
        self._hide_timer.stop()
        self._render()
    def append_token(self, token):
        self._raw += token
        self._render()
    def set_reply(self, text, sticker=None):
        self._set_sticker(sticker)
        self._raw = text
        self._render()
    def finish_reply(self):
        self._streaming = False
        self._hide_timer.start(max(12000, min(60000,len(self._raw)*220)))
    def show_message(self, text, *, duration_ms=15000, sticker=None, **_kwargs):
        self._set_sticker(sticker)
        self._raw = text
        self._render()
        if not self._streaming:
            self._hide_timer.start(max(8000,duration_ms))
    def _set_sticker(self, sticker_id):
        import time
        if not self._stickers_enabled:
            sticker_id = None
        if sticker_id and sticker_id != self._sticker_id and sticker_id == self._last_sticker_id and time.monotonic()-self._last_sticker_time < 30:
            sticker_id = None
        card = stickers.CATALOG.get(sticker_id)
        pix = QPixmap(str(resolve_resource_path('assets/stickers/'+sticker_id+'.png'))) if card else QPixmap()
        if pix.isNull():
            self._sticker_id = None
            self.sticker_image.clear()
            self.sticker_image.hide()
            self.sticker_caption.hide()
            return
        if sticker_id != self._sticker_id:
            self._last_sticker_id, self._last_sticker_time = sticker_id, time.monotonic()
        self._sticker_id = sticker_id
        self.sticker_image.setPixmap(pix.scaled(180,165,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        self.sticker_image.setFixedHeight(165)
        self.sticker_image.setAccessibleName(card['title'])
        self.sticker_caption.setText(card['title'])
        self.sticker_caption.setFixedHeight(38)
        self.sticker_image.show()
        self.sticker_caption.show()

    def enterEvent(self, event):
        self._hide_timer.stop()
        super().enterEvent(event)
    def leaveEvent(self, event):
        if not self._streaming:
            self.finish_reply()
        super().leaveEvent(event)
