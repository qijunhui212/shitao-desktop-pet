"""Drag-and-drop character pack import into 形象/ and validation."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from config.paths import app_root, resource_root

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}


def _has_sprite_files(folder: Path) -> bool:
    if not folder.is_dir():
        return False
    if any(folder.glob("*.png")) or any(folder.glob("*.gif")):
        return True
    gif_dir = folder / "gif"
    return gif_dir.is_dir() and any(gif_dir.glob("*.gif"))


def resolve_pack_folder(drop_path: Path) -> Path | None:
    """Pick the actual pack directory from a dropped folder path."""
    path = Path(drop_path).resolve()
    if not path.is_dir():
        return None
    if _has_sprite_files(path):
        return path

    subdirs = sorted(
        d for d in path.iterdir() if d.is_dir() and not d.name.startswith(".")
    )
    packs = [d for d in subdirs if _has_sprite_files(d)]
    if len(packs) == 1:
        return packs[0]
    if len(packs) > 1:
        return max(packs, key=lambda d: len(list(d.glob("*.png"))))
    return None


def is_image_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in _IMAGE_SUFFIXES


def resolve_drop_path(drop_path: Path) -> tuple[Path | None, str]:
    """
    Resolve drop to (pack_dir_or_file, kind).
    kind: folder | image | none
    """
    path = Path(drop_path).resolve()
    if is_image_file(path):
        return path, "image"
    if path.is_dir():
        pack = resolve_pack_folder(path)
        if pack:
            return pack, "folder"
    return None, "none"


def character_library_root() -> Path:
    root = resource_root()
    lib = root / "形象"
    if lib.is_dir():
        return lib
    lib = app_root() / "形象"
    lib.mkdir(parents=True, exist_ok=True)
    return lib


def _safe_pack_name(name: str) -> str:
    name = name.strip() or "新形象"
    return re.sub(r'[<>:"/\\|?*]', "_", name)[:64]


def _finalize_pack_dir(dest: Path) -> int:
    """Split single wide sprite sheet into 动作1.png, 动作2.png, ..."""
    from pet.sprite_sheet import split_pack_dir_if_sheet

    return split_pack_dir_if_sheet(dest)


def install_pack(source: Path, *, overwrite: bool = True) -> tuple[Path, str, int] | None:
    """
    Import folder or image into 形象/<name>/.
    Returns (installed_dir, pack_folder_name, slice_count) or None.
    slice_count > 1 means a horizontal sheet was auto-split.
    """
    src = Path(source).resolve()
    lib = character_library_root()

    if is_image_file(src):
        name = _safe_pack_name(src.stem)
        dest = lib / name
        try:
            if dest.exists():
                if not overwrite:
                    return None
                shutil.rmtree(dest)
            dest.mkdir(parents=True, exist_ok=True)
            from pet.sprite_sheet import split_horizontal_sheet, is_likely_horizontal_sheet
            from PySide6.QtGui import QImage

            img = QImage(str(src))
            slice_count = 0
            if is_likely_horizontal_sheet(img):
                names = split_horizontal_sheet(src, dest)
                slice_count = len(names)
            if slice_count < 2:
                shutil.copy2(src, dest / src.name)
                slice_count = 1
            return dest, name, slice_count
        except OSError:
            return None

    pack = resolve_pack_folder(src)
    if not pack:
        return None

    name = _safe_pack_name(pack.name)
    dest = lib / name

    try:
        if dest.resolve() == pack.resolve():
            slices = _finalize_pack_dir(dest)
            return dest, name, max(slices, len(list(dest.glob("*.png"))))
        if dest.exists():
            if not overwrite:
                return None
            shutil.rmtree(dest)
        shutil.copytree(pack, dest)
        slices = _finalize_pack_dir(dest)
        return dest, name, slices if slices >= 2 else len(list(dest.glob("*.png")))
    except OSError:
        return None
