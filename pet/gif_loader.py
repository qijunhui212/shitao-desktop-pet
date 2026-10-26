"""Load animated GIF frames as transparent QPixmaps (PuppyPal gray15 chroma)."""

from __future__ import annotations

import os
import tempfile
from collections import deque
from pathlib import Path

from PIL import Image, ImageSequence
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap

GRAY15 = (38, 38, 38)
GRAY_TOL = 14


def _is_chroma(r: int, g: int, b: int) -> bool:
    return all(abs(c - t) <= GRAY_TOL for c, t in zip((r, g, b), GRAY15))


def _remove_gray15(img: QImage) -> QImage:
    out = img.convertToFormat(QImage.Format.Format_ARGB32)
    w, h = out.width(), out.height()
    seeds: deque[tuple[int, int]] = deque()
    for x in range(w):
        for sx, sy in ((x, 0), (x, h - 1)):
            c = out.pixelColor(sx, sy)
            if c.alpha() and _is_chroma(c.red(), c.green(), c.blue()):
                seeds.append((sx, sy))
    for y in range(h):
        for sx, sy in ((0, y), (w - 1, y)):
            c = out.pixelColor(sx, sy)
            if c.alpha() and _is_chroma(c.red(), c.green(), c.blue()):
                seeds.append((sx, sy))
    while seeds:
        x, y = seeds.popleft()
        if x < 0 or x >= w or y < 0 or y >= h:
            continue
        c = out.pixelColor(x, y)
        if c.alpha() == 0:
            continue
        if not _is_chroma(c.red(), c.green(), c.blue()):
            continue
        c.setAlpha(0)
        out.setPixelColor(x, y, c)
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            seeds.append((nx, ny))
    return out


def _pil_frame_to_qpixmap(frame: Image.Image, max_height: int, chroma_gray15: bool) -> QPixmap:
    rgba = frame.convert("RGBA")
    tmp = Path(tempfile.gettempdir()) / f"petgif_{os.getpid()}_{id(frame)}.png"
    try:
        rgba.save(tmp)
        img = QImage(str(tmp))
    finally:
        tmp.unlink(missing_ok=True)
    if img.isNull():
        return QPixmap()
    if img.height() > max_height:
        img = img.scaledToHeight(max_height, Qt.TransformationMode.SmoothTransformation)
    if chroma_gray15:
        img = _remove_gray15(img)
    return QPixmap.fromImage(img)


def load_gif_pixmaps(
    path: str | Path,
    max_height: int,
    *,
    chroma_gray15: bool = True,
) -> tuple[list[QPixmap], list[int]]:
    """Return (frames, delay_ms_per_frame)."""
    gif_path = Path(path)
    if not gif_path.is_file():
        return [], []
    frames: list[QPixmap] = []
    delays: list[int] = []
    try:
        with Image.open(gif_path) as gif:
            for frame in ImageSequence.Iterator(gif):
                pix = _pil_frame_to_qpixmap(frame, max_height, chroma_gray15)
                if pix.isNull():
                    continue
                frames.append(pix)
                delays.append(int(frame.info.get("duration", 100) or 100))
    except Exception:
        return [], []
    if not delays and frames:
        delays = [100] * len(frames)
    return frames, delays
