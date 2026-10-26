"""Split horizontal sprite sheets (one PNG, many characters) into separate files."""

from __future__ import annotations

import random
from collections import deque
from pathlib import Path

from PySide6.QtGui import QImage

_MAX_KMEANS_SAMPLES = 24_000


def _pixel_opaque(img: QImage, x: int, y: int, alpha_min: int = 12) -> bool:
    c = img.pixelColor(x, y)
    if c.alpha() < alpha_min:
        return False
    if c.alpha() > 250 and c.red() > 245 and c.green() > 245 and c.blue() > 245:
        return False
    return True


def _crop_to_content(img: QImage, pad: int = 4) -> QImage:
    w, h = img.width(), img.height()
    min_x, min_y, max_x, max_y = w, h, 0, 0
    found = False
    for y in range(h):
        for x in range(w):
            if _pixel_opaque(img, x, y):
                found = True
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    if not found:
        return img
    min_x = max(0, min_x - pad)
    min_y = max(0, min_y - pad)
    max_x = min(w - 1, max_x + pad)
    max_y = min(h - 1, max_y + pad)
    return img.copy(min_x, min_y, max_x - min_x + 1, max_y - min_y + 1)


def _find_horizontal_slices(
    img: QImage,
    *,
    min_slice_width: int = 20,
) -> list[tuple[int, int, int, int]]:
    """Split at fully transparent vertical gaps."""
    w, h = img.width(), img.height()
    if w < 2 or h < 2:
        return []

    col_has = [any(_pixel_opaque(img, x, y) for y in range(h)) for x in range(w)]
    slices: list[tuple[int, int, int, int]] = []
    in_seg = False
    start = 0

    for x in range(w):
        if col_has[x]:
            if not in_seg:
                start = x
                in_seg = True
        else:
            if in_seg:
                width = x - start
                if width >= min_slice_width:
                    slices.append((start, 0, width, h))
                in_seg = False

    if in_seg:
        width = w - start
        if width >= min_slice_width:
            slices.append((start, 0, width, h))

    return slices


def _find_component_slices(
    img: QImage,
    *,
    step: int = 2,
    min_area: int = 600,
) -> list[tuple[int, int, int, int]]:
    """Each disconnected sprite → one box (cats side by side with touching edges)."""
    w, h = img.width(), img.height()
    if w < 4 or h < 4:
        return []

    gw = (w + step - 1) // step
    gh = (h + step - 1) // step
    grid = [
        [_pixel_opaque(img, min(w - 1, gx * step), min(h - 1, gy * step)) for gx in range(gw)]
        for gy in range(gh)
    ]
    visited = [[False] * gw for _ in range(gh)]
    boxes: list[tuple[int, int, int, int]] = []

    for gy in range(gh):
        for gx in range(gw):
            if not grid[gy][gx] or visited[gy][gx]:
                continue
            q = deque([(gx, gy)])
            visited[gy][gx] = True
            min_gx = max_gx = gx
            min_gy = max_gy = gy
            while q:
                cx, cy = q.popleft()
                min_gx = min(min_gx, cx)
                max_gx = max(max_gx, cx)
                min_gy = min(min_gy, cy)
                max_gy = max(max_gy, cy)
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nx, ny = cx + dx, cy + dy
                    if (
                        0 <= nx < gw
                        and 0 <= ny < gh
                        and grid[ny][nx]
                        and not visited[ny][nx]
                    ):
                        visited[ny][nx] = True
                        q.append((nx, ny))

            x0 = min_gx * step
            y0 = min_gy * step
            x1 = min(w, (max_gx + 1) * step)
            y1 = min(h, (max_gy + 1) * step)
            if (x1 - x0) * (y1 - y0) >= min_area:
                boxes.append((x0, y0, x1 - x0, y1 - y0))

    boxes.sort(key=lambda b: b[0] + b[2] // 2)
    return boxes


def _find_valley_slices(img: QImage) -> list[tuple[int, int, int, int]]:
    """Split at columns with very few opaque pixels."""
    w, h = img.width(), img.height()
    counts = [sum(1 for y in range(h) if _pixel_opaque(img, x, y)) for x in range(w)]
    if not counts or max(counts) == 0:
        return []

    threshold = max(2, int(max(counts) * 0.06))
    slices: list[tuple[int, int, int, int]] = []
    in_seg = False
    start = 0

    for x in range(w):
        if counts[x] > threshold:
            if not in_seg:
                start = x
                in_seg = True
        else:
            if in_seg:
                width = x - start
                if width >= 20:
                    slices.append((start, 0, width, h))
                in_seg = False
    if in_seg:
        width = w - start
        if width >= 20:
            slices.append((start, 0, width, h))

    return slices


def _collect_opaque_x_samples(img: QImage) -> list[int]:
    w, h = img.width(), img.height()
    xs = [x for y in range(h) for x in range(w) if _pixel_opaque(img, x, y)]
    if len(xs) <= _MAX_KMEANS_SAMPLES:
        return xs
    rng = random.Random(0)
    return rng.sample(xs, _MAX_KMEANS_SAMPLES)


def _kmeans_1d(xs: list[int], k: int, *, iters: int = 28) -> list[float]:
    if k < 1 or not xs:
        return []
    k = min(k, len(xs))
    centers = [float(xs[(len(xs) * i) // k]) for i in range(k)]
    for _ in range(iters):
        groups: list[list[int]] = [[] for _ in range(k)]
        for v in xs:
            j = min(range(k), key=lambda i: abs(v - centers[i]))
            groups[j].append(v)
        new = [sum(g) / len(g) if g else centers[i] for i, g in enumerate(groups)]
        if new == centers:
            break
        centers = new
    return sorted(centers)


def _cluster_balance_ratio(xs: list[int], k: int) -> float:
    if k < 2 or not xs:
        return 999.0
    centers = [float(xs[(len(xs) * i) // k]) for i in range(k)]
    for _ in range(28):
        groups: list[list[int]] = [[] for _ in range(k)]
        for v in xs:
            j = min(range(k), key=lambda i: abs(v - centers[i]))
            groups[j].append(v)
        centers = [sum(g) / len(g) if g else centers[i] for i, g in enumerate(groups)]
    sizes = sorted(len(g) for g in groups)
    if not sizes or min(sizes) == 0:
        return 999.0
    return sizes[-1] / sizes[0]


def _estimate_cluster_count(xs: list[int], width: int, height: int) -> int:
    """Guess how many sprites are in a row (touching / no transparent gaps)."""
    if not xs or width < 80:
        return 2
    aspect_cap = max(3, int(width / max(height, 1)) + 4)
    max_k = min(12, max(2, width // 40), aspect_cap)
    best_k = 2
    min_gap = max(24, int(width * 0.05))

    for k in range(2, max_k + 1):
        centers = _kmeans_1d(xs, k)
        if len(centers) < 2:
            break
        gaps = [centers[i + 1] - centers[i] for i in range(len(centers) - 1)]
        if min(gaps) < min_gap:
            break
        if _cluster_balance_ratio(xs, k) > 1.15:
            break
        best_k = k

    return best_k


def _find_kmeans_slices(img: QImage) -> list[tuple[int, int, int, int]]:
    """Split when sprites touch but are evenly spaced along X."""
    w, h = img.width(), img.height()
    if w < int(h * 1.25):
        return []

    xs = _collect_opaque_x_samples(img)
    if len(xs) < 80:
        return []

    count = _estimate_cluster_count(xs, w, h)
    if count < 2:
        return []

    centers = _kmeans_1d(xs, count)
    if len(centers) < 2:
        return []

    bounds = [0]
    for i in range(len(centers) - 1):
        bounds.append(int(round((centers[i] + centers[i + 1]) / 2)))
    bounds.append(w)

    slices: list[tuple[int, int, int, int]] = []
    for i in range(len(bounds) - 1):
        x0, x1 = bounds[i], bounds[i + 1]
        width = x1 - x0
        if width >= 16:
            slices.append((x0, 0, width, h))
    return slices


def _estimate_equal_slices(img: QImage, count: int | None = None) -> list[tuple[int, int, int, int]]:
    w, h = img.width(), img.height()
    if w < int(h * 1.4):
        return []
    if count is None:
        count = max(2, min(12, round(w / max(h * 0.75, 1))))
    slice_w = w // count
    if slice_w < 16:
        return []
    return [
        (i * slice_w, 0, slice_w if i < count - 1 else w - i * slice_w, h)
        for i in range(count)
    ]


def _resolve_slices(img: QImage) -> list[tuple[int, int, int, int]]:
    for finder in (_find_horizontal_slices, _find_component_slices, _find_valley_slices):
        slices = finder(img)
        if len(slices) >= 2:
            return slices

    comp = _find_component_slices(img, step=1)
    if len(comp) >= 2:
        return comp

    kmeans = _find_kmeans_slices(img)
    if len(kmeans) >= 2:
        return kmeans

    xs = _collect_opaque_x_samples(img)
    count = _estimate_cluster_count(xs, img.width(), img.height()) if xs else None
    return _estimate_equal_slices(img, count=count)


def is_likely_horizontal_sheet(img: QImage) -> bool:
    if img.isNull():
        return False
    w, h = img.width(), img.height()
    if w < max(180, int(h * 1.15)):
        return False
    return len(_resolve_slices(img)) >= 2


def split_horizontal_sheet(
    src: Path,
    out_dir: Path,
    *,
    name_prefix: str = "动作",
) -> list[str]:
    img = QImage(str(src))
    if img.isNull():
        return []

    if img.format() != QImage.Format.Format_ARGB32:
        img = img.convertToFormat(QImage.Format.Format_ARGB32)

    slices = _resolve_slices(img)
    if len(slices) < 2:
        return []

    out_dir.mkdir(parents=True, exist_ok=True)
    saved: list[str] = []

    for i, (x, y, sw, sh) in enumerate(slices, start=1):
        part = img.copy(x, y, sw, sh)
        part = _crop_to_content(part)
        if part.width() < 8 or part.height() < 8:
            continue
        name = f"{name_prefix}{i}"
        if part.save(str(out_dir / f"{name}.png"), "PNG"):
            saved.append(name)

    return saved


def split_pack_dir_if_sheet(pack_dir: Path) -> int:
    pngs = sorted(pack_dir.glob("*.png"))
    if len(pngs) != 1:
        return 0
    src = pngs[0]
    img = QImage(str(src))
    if not is_likely_horizontal_sheet(img):
        return 0
    names = split_horizontal_sheet(src, pack_dir)
    if len(names) >= 2:
        try:
            src.unlink()
        except OSError:
            pass
        return len(names)
    return 0
