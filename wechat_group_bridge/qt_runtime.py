from __future__ import annotations

from queue import Empty, Queue
from threading import Event
import time

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot

from .models import BridgeSettings


class _GroupListener(QObject):
    incoming = Signal(object)
    status = Signal(str)
    error = Signal(str)
    stopped = Signal()

    def __init__(self, settings: BridgeSettings, transport_factory=None):
        super().__init__()
        self._settings = settings.validated()
        self._transport_factory = transport_factory
        self._stop_event = Event()
        self._outgoing: Queue[str] = Queue(maxsize=4)
        self._transport = None
        self.memory_error = ''
        self._memory_service = None

    @property
    def memory_scope(self):
        return getattr(self._transport, 'memory_scope', ('', ''))

    def enqueue(self, text: str) -> None:
        try:
            self._outgoing.put_nowait(text)
        except Exception:
            self.error.emit("待发送队列已满，未发送新消息。")

    def request_stop(self) -> None:
        self._stop_event.set()
        if self._memory_service:
            self._memory_service.stop()
        if self._transport and hasattr(self._transport, 'cancel'):
            self._transport.cancel()

    @Slot()
    def run(self) -> None:
        try:
            factory = self._transport_factory
            if factory is None:
                try:
                    from .native_transport import NativeGroupTransport
                except ImportError as exc:
                    raise RuntimeError("微信接入可选依赖未安装，请查看 README。普通桌宠聊天不受影响。") from exc
                factory = NativeGroupTransport
            self._transport = factory(self._settings)
            if self._stop_event.is_set():
                return
            self._transport.start()
            if self._stop_event.is_set():
                return
            mention = getattr(self._transport, 'mention_label', self._settings.mention_text)
            store = None
            if self._settings.hourly_memory_enabled:
                try:
                    from .group_memory import GroupMemoryStore
                    from .memory_summary import HourlyMemoryService
                    store = GroupMemoryStore()
                    self._memory_service = HourlyMemoryService(store, self._settings.group_name)
                    self._memory_service.start()
                except Exception:
                    self.memory_error = '群记忆存储暂时不可用；文字回复仍可使用。'
            self.status.emit(f"后台已接入「{self._settings.group_name}」· 等待新的 {mention}")
            while not self._stop_event.is_set():
                while not self._stop_event.is_set():
                    try:
                        text = self._outgoing.get_nowait()
                    except Empty:
                        break
                    if self._settings.auto_reply_enabled or self._settings.idle_announcement_enabled:
                        result = self._transport.send(text)
                        if result:
                            self.status.emit(result)
                for message in self._transport.poll():
                    if self._stop_event.is_set():
                        break
                    if store is not None:
                        try:
                            store.record(message)
                            self.memory_error = ''
                        except Exception:
                            self.memory_error = '新消息写入群记忆失败，请检查磁盘空间；文字回复仍可使用。'
                    self.incoming.emit(message)
                self._stop_event.wait(0.35)
        except Exception as exc:
            if not self._stop_event.is_set():
                self.error.emit(str(exc))
        finally:
            if self._memory_service:
                self._memory_service.stop()
            try:
                if self._transport:
                    self._transport.stop()
            except Exception as exc:
                self.error.emit(str(exc))
            self.status.emit("已停止监听")
            self.stopped.emit()


class WechatBridgeRuntime(QObject):
    """Owns one background listener and a bounded outbound queue."""

    incoming = Signal(object)
    status = Signal(str)
    error = Signal(str)

    def __init__(self, settings: BridgeSettings, parent=None, transport_factory=None):
        super().__init__(parent)
        self._thread = QThread(self)
        self._worker = _GroupListener(settings, transport_factory=transport_factory)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.incoming.connect(self.incoming, Qt.ConnectionType.QueuedConnection)
        self._worker.status.connect(self.status, Qt.ConnectionType.QueuedConnection)
        self._worker.error.connect(self.error, Qt.ConnectionType.QueuedConnection)
        self._worker.stopped.connect(self._thread.quit, Qt.ConnectionType.DirectConnection)
        self._thread.finished.connect(self._worker.deleteLater)
        self._started = False

    def start(self) -> None:
        if not self._started:
            self._started = True
            self._thread.start()

    def send(self, text: str) -> None:
        if self._thread.isRunning():
            self._worker.enqueue(text)

    def stop(self, timeout_ms: int = 5000) -> bool:
        self._worker.request_stop()
        return self._thread.wait(timeout_ms)

    @property
    def is_running(self) -> bool:
        return self._thread.isRunning()

    @property
    def memory_scope(self):
        return self._worker.memory_scope

    @property
    def memory_error(self):
        return self._worker.memory_error
