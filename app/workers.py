from PySide6.QtCore import QObject, Signal

from brain.chat import ChatCancelled
from brain.chat_errors import friendly_chat_error


class ChatWorker(QObject):
    finished = Signal(str, object, object)  # display, reminder_action, memory_action
    cancelled = Signal(str)  # partial display
    token = Signal(str)
    error = Signal(str)

    def __init__(self, chat_service, user_text: str, reminders: list, cancel_flag: list):
        super().__init__()
        self._chat = chat_service
        self._text = user_text
        self._reminders = reminders
        self._cancel_flag = cancel_flag

    def run(self) -> None:
        try:
            display, reminder, memory = self._chat.chat_stream(
                self._text,
                self._reminders,
                on_token=lambda t: self.token.emit(t),
                should_cancel=lambda: bool(self._cancel_flag[0]),
            )
            self.finished.emit(display, reminder, memory)
        except ChatCancelled as e:
            self.cancelled.emit(e.partial_display or "")
        except Exception as e:
            self.error.emit(friendly_chat_error(e))
