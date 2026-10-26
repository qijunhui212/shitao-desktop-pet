"""Looping GIF playback via QTimer or external drive (走动时与位移同步，避免 Windows 透明窗卡住)."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtGui import QPixmap

from pet.gif_loader import load_gif_pixmaps


class GifClip(QObject):
    frame_ready = Signal(QPixmap)
    finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._frames: list[QPixmap] = []
        self._delays: list[int] = []
        self._index = 0
        self._loop = True
        self._external_drive = False
        self._pending_ms = 0
        self._source_path = ""
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance)

    @property
    def has_frames(self) -> bool:
        return bool(self._frames)

    @property
    def poster(self) -> QPixmap:
        return self._frames[0] if self._frames else QPixmap()

    @property
    def is_playing(self) -> bool:
        return self._external_drive or self._timer.isActive()

    def load(self, path: str, max_height: int, *, chroma_gray15: bool = True) -> bool:
        self.stop()
        self._source_path = path
        frames, delays = load_gif_pixmaps(path, max_height, chroma_gray15=chroma_gray15)
        if not frames:
            self._frames = []
            self._delays = []
            return False
        self._frames = frames
        self._delays = delays
        return True

    def start(self, *, loop: bool = True, external_drive: bool = False) -> None:
        self._loop = loop
        self._external_drive = external_drive
        self._index = 0
        self._pending_ms = 0
        self._timer.stop()
        if not self._frames:
            return
        self.frame_ready.emit(self._frames[0])
        if not external_drive:
            self._schedule_next()

    def stop(self) -> None:
        self._timer.stop()
        self._external_drive = False
        self._pending_ms = 0

    def resume_timer_drive(self) -> None:
        """走动结束或取消后恢复定时器驱动。"""
        self._external_drive = False
        self._pending_ms = 0
        if self._frames:
            self._schedule_next()

    def tick_external(self, elapsed_ms: int) -> None:
        """由 PetController 位移节拍驱动，与窗口 move 同一事件循环内换帧。"""
        if not self._external_drive or not self._frames:
            return
        self._pending_ms += max(1, elapsed_ms)
        while self._pending_ms >= self._frame_delay():
            self._pending_ms -= self._frame_delay()
            if not self._advance_index():
                break

    def _frame_delay(self) -> int:
        if not self._delays:
            return 100
        if self._index < len(self._delays):
            return max(20, self._delays[self._index])
        return 100

    def _schedule_next(self) -> None:
        if not self._frames or self._external_drive:
            return
        self._timer.start(self._frame_delay())

    def _advance_index(self) -> bool:
        if not self._frames:
            return False
        nxt = self._index + 1
        if nxt >= len(self._frames):
            if self._loop:
                nxt = 0
            else:
                return False
        self._index = nxt
        self.frame_ready.emit(self._frames[self._index])
        return True

    def _advance(self) -> None:
        if not self._frames or self._external_drive:
            return
        self._timer.stop()
        if self._advance_index():
            self._schedule_next()
        else:
            self.finished.emit()
