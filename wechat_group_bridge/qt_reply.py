from __future__ import annotations

from threading import Event

from PySide6.QtCore import QObject, Signal, Slot

from .models import IncomingGroupMessage


class GroupReplyRelay(QObject):
    """A main-thread Qt receiver; bare Python lambdas run in the worker thread."""
    def __init__(self, owner, session_id):
        super().__init__(owner)
        self._owner = owner
        self._session_id = session_id

    @Slot(object, str, bool)
    def finished(self, message, text, idle):
        if self._session_id == self._owner._wechat_session_id:
            self._owner._on_wechat_reply_finished(message, text, idle)

    @Slot(object, str, bool)
    def failed(self, message, error, idle):
        if self._session_id == self._owner._wechat_session_id:
            self._owner._on_wechat_reply_failed(message, error, idle)


class GroupReplyWorker(QObject):
    finished = Signal(object, str, bool)
    failed = Signal(object, str, bool)

    def __init__(self, engine, message: IncomingGroupMessage, text: str, cancel_event: Event | None = None, idle: bool = False):
        super().__init__()
        self._engine = engine
        self._message = message
        self._text = text
        self._cancel_event = cancel_event or Event()
        self._idle = idle

    @Slot()
    def run(self) -> None:
        try:
            if self._idle:
                reply = self._engine.idle_message(self._message.group_name, self._cancel_event,
                    memory_scope=(self._message.account_id,self._message.group_id))
            else:
                reply = self._engine.reply(self._message, self._text, self._cancel_event)
            self.finished.emit(self._message, reply, self._idle)
        except Exception as exc:
            self.failed.emit(self._message, str(exc), self._idle)
