"""向已有形象包写入人设、食物等资源（不改变 install_pack 主流程）。"""

from __future__ import annotations

import shutil
from pathlib import Path

from pet.pack_drop import is_image_file
from pet.pack_food import FOOD_DIR_NAMES, FOOD_LIST_FILENAMES, invalidate_food_catalog

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}
_PERSONA_SUFFIXES = {".txt", ".md"}
_PERSONA_TARGET = "人设.txt"


def _food_dir(pack_dir: Path) -> Path:
    for name in FOOD_DIR_NAMES:
        path = pack_dir / name
        if path.is_dir():
            return path
    dest = pack_dir / "食物"
    dest.mkdir(parents=True, exist_ok=True)
    return dest


def install_persona_file(pack_dir: Path, source: Path) -> tuple[bool, str]:
    """复制人设到 pack_dir/人设.txt。"""
    src = Path(source).resolve()
    if not src.is_file() or src.suffix.lower() not in _PERSONA_SUFFIXES:
        return False, "请选择 .txt 人设文件"
    if not pack_dir.is_dir():
        return False, "当前形象包目录不存在"
    dest = pack_dir / _PERSONA_TARGET
    try:
        shutil.copy2(src, dest)
    except OSError as e:
        return False, f"写入失败：{e}"
    return True, f"已写入 {dest.name}"


def install_food_folder(pack_dir: Path, source: Path) -> tuple[bool, str, int]:
    """将文件夹内食物图片复制到 pack/食物/，并移除 食物.txt 清单。"""
    src = Path(source).resolve()
    if not src.is_dir():
        return False, "请选择食物文件夹", 0
    if not pack_dir.is_dir():
        return False, "当前形象包目录不存在", 0

    food_dir = _food_dir(pack_dir)
    for name in FOOD_LIST_FILENAMES:
        manifest = pack_dir / name
        if manifest.is_file():
            try:
                manifest.unlink()
            except OSError:
                pass

    count = 0
    for item in sorted(src.rglob("*")):
        if not item.is_file() or not is_image_file(item):
            continue
        try:
            shutil.copy2(item, food_dir / item.name)
            count += 1
        except OSError:
            continue

    if count == 0:
        return False, "文件夹内未找到 PNG/GIF 等食物图片", 0

    invalidate_food_catalog()
    return True, f"已导入 {count} 个食物到 {food_dir.name}/", count
