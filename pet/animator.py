from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPixmap, QTransform
from PySide6.QtWidgets import QLabel, QWidget

from config.settings import PET_HEIGHT, PET_WIDTH, ROOT
from pet.controller import PetState


def _make_placeholder_pixmap(facing: int = 1) -> QPixmap:
    """Draw a simple chibi placeholder until real sprites are added."""
    w, h = PET_WIDTH, PET_HEIGHT
    pix = QPixmap(w, h)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    if facing < 0:
        p.translate(w, 0)
        p.scale(-1, 1)

    # body / hanfu cream robe
    p.setBrush(QColor("#F5E6C8"))
    p.setPen(QColor("#2C1810"))
    p.drawEllipse(36, 70, 56, 70)

    # collar
    p.setBrush(QColor("#1A1A2E"))
    p.drawEllipse(48, 78, 32, 20)

    # head
    p.setBrush(QColor("#FFE4D0"))
    p.drawEllipse(40, 18, 48, 52)

    # hair
    p.setBrush(QColor("#3D2314"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(38, 12, 52, 36)
    p.setBrush(QColor("#FFE4D0"))
    p.drawEllipse(42, 28, 44, 36)

    # flower
    p.setBrush(QColor("#E8A0BF"))
    p.setPen(QColor("#C77DFF"))
    p.drawEllipse(72, 22, 22, 22)
    p.setBrush(QColor("#FFB4C8"))
    p.drawEllipse(76, 26, 14, 14)

    # eyes
    p.setBrush(QColor("#333"))
    p.drawEllipse(52, 42, 6, 8)
    p.drawEllipse(68, 42, 6, 8)

    p.end()
    return pix


class PetSprite(QLabel):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedSize(PET_WIDTH, PET_HEIGHT)
        self._state = PetState.IDLE
        self._facing = 1
        self._walk_frame = 0
        self._assets_dir = ROOT / "assets" / "character"
        self._idle_frames: list[QPixmap] = []
        self._walk_frames: list[QPixmap] = []
        self._load_assets()
        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._next_frame)
        self._anim_timer.start(200)
        self._refresh()

    def _load_assets(self) -> None:
        if not self._assets_dir.is_dir():
            return
        idle = sorted(self._assets_dir.glob("idle_*.png"))
        walk = sorted(self._assets_dir.glob("walk_*.png"))
        if idle:
            self._idle_frames = [px for p in idle if not (px := QPixmap(str(p))).isNull()]
        if walk:
            self._walk_frames = [px for p in walk if not (px := QPixmap(str(p))).isNull()]

    def set_facing(self, facing: int) -> None:
        if self._facing != facing:
            self._facing = facing
            self._refresh()

    def set_state(self, state: PetState) -> None:
        self._state = state
        self._refresh()

    def _next_frame(self) -> None:
        if getattr(self, "_state", PetState.IDLE) == PetState.WALK and self._walk_frames:
            self._walk_frame = (self._walk_frame + 1) % len(self._walk_frames)
            self._refresh()
        elif self._idle_frames:
            self._walk_frame = (self._walk_frame + 1) % len(self._idle_frames)
            self._refresh()

    def _refresh(self) -> None:
        state = getattr(self, "_state", PetState.IDLE)
        frames = self._walk_frames if state == PetState.WALK and self._walk_frames else self._idle_frames
        if frames:
            idx = self._walk_frame % len(frames)
            pix = frames[idx]
            if self._facing < 0:
                pix = pix.transformed(QTransform().scale(-1, 1))
            self.setPixmap(pix.scaled(self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        else:
            self.setPixmap(_make_placeholder_pixmap(self._facing))

    def current_pixmap(self) -> QPixmap:
        px = super().pixmap()
        return px if px and not px.isNull() else _make_placeholder_pixmap(self._facing)
