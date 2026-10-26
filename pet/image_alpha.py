"""Remove backgrounds and clean edges for desktop pet sprites."""

from __future__ import annotations

import os
from collections import deque
from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap


class MatteMode(str, Enum):
    OFF = "off"
    SAFE = "safe"
    NORMAL = "normal"


def _get_matte_mode() -> MatteMode:
    raw = os.getenv("CHARACTER_MATTE", "safe").strip().lower()
    for mode in MatteMode:
        if raw == mode.value:
            return mode
    return MatteMode.SAFE


def _matte_dark_bg() -> bool:
    return os.getenv("CHARACTER_MATTE_DARK", "1").strip() not in ("0", "false", "no")


def _defringe_enabled() -> bool:
    default = "0" if _get_matte_mode() == MatteMode.OFF else "1"
    return os.getenv("CHARACTER_DEFRINGE", default).strip() not in ("0", "false", "no")


def _is_light_bg_pixel(r: int, g: int, b: int, mode: MatteMode, *, seed: bool = False) -> bool:
    mx, mn = max(r, g, b), min(r, g, b)
    sat = mx - mn
    avg = (r + g + b) / 3
    if seed and mode == MatteMode.SAFE:
        return mx >= 253 and sat <= 6
    if seed and mode == MatteMode.NORMAL:
        return mx >= 248 and sat <= 10 and avg >= 246
    if mode == MatteMode.SAFE:
        return (avg >= 254 and sat <= 5) or (238 <= avg <= 252 and sat <= 8)
    if mx < 200 or sat > 28:
        return False
    return avg >= 242


def _is_dark_bg_pixel(r: int, g: int, b: int, *, seed: bool = False) -> bool:
    avg = (r + g + b) / 3
    mx, mn = max(r, g, b), min(r, g, b)
    sat = mx - mn
    # 深蓝 / 深灰 AI 导出底
    if avg <= 35:
        return True
    if seed:
        return avg <= 90 and sat <= 35
    if avg <= 85 and sat <= 40:
        return True
    if b > r + 12 and b > g + 8 and avg < 130:
        return True
    return False


def _is_bg_pixel(r: int, g: int, b: int, mode: MatteMode, *, seed: bool = False) -> bool:
    if _is_light_bg_pixel(r, g, b, mode, seed=seed):
        return True
    if _matte_dark_bg() and _is_dark_bg_pixel(r, g, b, seed=seed):
        return True
    return False


def _flood_remove_background(img: QImage, mode: MatteMode) -> QImage:
    w, h = img.width(), img.height()
    seeds: deque[tuple[int, int]] = deque()

    for x in range(w):
        for sx, sy in ((x, 0), (x, h - 1)):
            c = img.pixelColor(sx, sy)
            if c.alpha() and _is_bg_pixel(c.red(), c.green(), c.blue(), mode, seed=True):
                seeds.append((sx, sy))
    for y in range(h):
        for sx, sy in ((0, y), (w - 1, y)):
            c = img.pixelColor(sx, sy)
            if c.alpha() and _is_bg_pixel(c.red(), c.green(), c.blue(), mode, seed=True):
                seeds.append((sx, sy))

    while seeds:
        x, y = seeds.popleft()
        if x < 0 or x >= w or y < 0 or y >= h:
            continue
        c = img.pixelColor(x, y)
        if c.alpha() == 0:
            continue
        if not _is_bg_pixel(c.red(), c.green(), c.blue(), mode, seed=False):
            continue
        c.setAlpha(0)
        img.setPixelColor(x, y, c)
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            seeds.append((nx, ny))
    return img


def _remove_white_fringe(img: QImage) -> QImage:
    """去掉贴边半透明白边 / 白晕。"""
    w, h = img.width(), img.height()
    neighbors = ((1, 0), (-1, 0), (0, 1), (0, -1))

    for y in range(h):
        for x in range(w):
            c = img.pixelColor(x, y)
            if c.alpha() == 0:
                continue
            r, g, b, a = c.red(), c.green(), c.blue(), c.alpha()
            if r < 210 or g < 210 or b < 210:
                continue
            near_hole = False
            for dx, dy in neighbors:
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h:
                    if img.pixelColor(nx, ny).alpha() < 40:
                        near_hole = True
                        break
            if near_hole or a < 220:
                c.setAlpha(0)
                img.setPixelColor(x, y, c)
    return img


def _defringe_light_spill(img: QImage) -> QImage:
    """降低边缘浅色溢色。"""
    w, h = img.width(), img.height()
    for y in range(h):
        for x in range(w):
            c = img.pixelColor(x, y)
            a = c.alpha()
            if a == 0 or a == 255:
                continue
            r, g, b = c.red(), c.green(), c.blue()
            if r > 200 and g > 200 and b > 200:
                k = a / 255.0
                c.setRed(int(r * k))
                c.setGreen(int(g * k))
                c.setBlue(int(b * k))
                img.setPixelColor(x, y, c)
    return img


def _feather_alpha(img: QImage, passes: int = 1) -> QImage:
    w, h = img.width(), img.height()
    for _ in range(passes):
        copy = img.copy()
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                c = copy.pixelColor(x, y)
                if c.alpha() == 0:
                    continue
                total = 0
                count = 0
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        total += copy.pixelColor(x + dx, y + dy).alpha()
                        count += 1
                c.setAlpha(total // count)
                img.setPixelColor(x, y, c)
    return img


def remove_background(image: QImage, mode: MatteMode | None = None) -> QImage:
    mode = mode or _get_matte_mode()
    if mode == MatteMode.OFF:
        return image.convertToFormat(QImage.Format.Format_ARGB32)

    img = image.convertToFormat(QImage.Format.Format_ARGB32)
    img = _flood_remove_background(img, mode)
    if _defringe_enabled():
        img = _remove_white_fringe(img)
        img = _defringe_light_spill(img)
        passes = int(os.getenv("CHARACTER_ALPHA_FEATHER", "1"))
        if passes > 0:
            img = _feather_alpha(img, min(passes, 3))
    return _crop_to_content(img)


def _crop_to_content(img: QImage) -> QImage:
    w, h = img.width(), img.height()
    min_x, min_y = w, h
    max_x, max_y = 0, 0
    found = False
    for y in range(h):
        for x in range(w):
            if img.pixelColor(x, y).alpha() > 8:
                found = True
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    if not found:
        return img
    pad = 2
    min_x = max(0, min_x - pad)
    min_y = max(0, min_y - pad)
    max_x = min(w - 1, max_x + pad)
    max_y = min(h - 1, max_y + pad)
    return img.copy(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)


def _has_real_transparency(image: QImage) -> bool:
    step = max(1, min(image.width(), image.height()) // 32)
    transparent = 0
    samples = 0
    for y in range(0, image.height(), step):
        for x in range(0, image.width(), step):
            samples += 1
            if image.pixelColor(x, y).alpha() < 200:
                transparent += 1
    return samples > 0 and transparent / samples > 0.05


def _post_process(img: QImage) -> QImage:
    if not _defringe_enabled():
        return img
    img = _remove_white_fringe(img)
    img = _defringe_light_spill(img)
    passes = int(os.getenv("CHARACTER_ALPHA_FEATHER", "1"))
    if passes > 0:
        img = _feather_alpha(img, min(passes, 3))
    return img


def load_transparent_pixmap(path: str, max_height: int) -> QPixmap:
    image = QImage(path)
    if image.isNull():
        return QPixmap()
    if image.height() > max_height:
        image = image.scaledToHeight(
            max_height,
            Qt.TransformationMode.SmoothTransformation,
        )
    mode = _get_matte_mode()
    if mode == MatteMode.OFF:
        img = image.convertToFormat(QImage.Format.Format_ARGB32)
        return QPixmap.fromImage(_post_process(img))
    if image.hasAlphaChannel() and _has_real_transparency(image):
        return QPixmap.fromImage(_post_process(image.convertToFormat(QImage.Format.Format_ARGB32)))
    return QPixmap.fromImage(remove_background(image, mode))
