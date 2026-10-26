"""设置页拖放导入：自动判定形象包 / 人设 / 食物。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pet.pack_drop import _has_sprite_files, is_image_file
from pet.pack_food import FOOD_DIR_NAMES
from pet.pack_prompt import find_pack_prompt_file

_PERSONA_SUFFIXES = {".txt", ".md"}


def is_food_dir_name(name: str) -> bool:
    lower = name.lower()
    return name in FOOD_DIR_NAMES or lower in {n.lower() for n in FOOD_DIR_NAMES}


def _dir_has_images(folder: Path) -> bool:
    if not folder.is_dir():
        return False
    for pattern in ("*.png", "*.jpg", "*.jpeg", "*.webp", "*.bmp", "*.gif"):
        if any(folder.glob(pattern)):
            return True
    return False


def has_food_content(folder: Path) -> bool:
    """文件夹内是否含食物图（且不是立绘包）。"""
    if not folder.is_dir():
        return False
    if is_food_dir_name(folder.name) and _dir_has_images(folder):
        return True
    for name in FOOD_DIR_NAMES:
        sub = folder / name
        if sub.is_dir() and _dir_has_images(sub):
            return True
    if has_character_sprites(folder):
        return False
    if find_pack_prompt_file(folder):
        return False
    return _dir_has_images(folder)


def has_character_sprites(folder: Path) -> bool:
    """是否含立绘（排除纯 食物/ 目录）。"""
    if not folder.is_dir() or is_food_dir_name(folder.name):
        return False
    if any(folder.glob("*.gif")):
        return True
    gif_dir = folder / "gif"
    if gif_dir.is_dir() and any(gif_dir.glob("*.gif")):
        return True
    root_pngs = list(folder.glob("*.png"))
    if len(root_pngs) >= 2:
        return True
    if len(root_pngs) == 1 and find_pack_prompt_file(folder):
        return True
    for child in sorted(folder.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if is_food_dir_name(child.name):
            continue
        if _has_sprite_files(child):
            return True
    return False


def resolve_persona_source(path: Path) -> Path | None:
    path = path.resolve()
    if path.is_file() and path.suffix.lower() in _PERSONA_SUFFIXES:
        return path
    if path.is_dir():
        return find_pack_prompt_file(path)
    return None


def resolve_food_source(path: Path) -> Path | None:
    path = path.resolve()
    if not path.is_dir():
        return None
    if has_food_content(path):
        return path
    return None


def _kinds_for_path(path: Path) -> set[str]:
    path = path.resolve()
    kinds: set[str] = set()
    if not path.exists():
        return kinds

    if is_image_file(path):
        kinds.add("pack")
        return kinds

    if path.is_file():
        if resolve_persona_source(path):
            kinds.add("persona")
        return kinds

    if not path.is_dir():
        return kinds

    if has_character_sprites(path):
        kinds.add("pack")
        return kinds

    if resolve_persona_source(path):
        kinds.add("persona")
    if has_food_content(path):
        kinds.add("food")
    return kinds


@dataclass
class ImportDropPlan:
    pack: Path | None = None
    persona: Path | None = None
    food: Path | None = None

    def is_empty(self) -> bool:
        return self.pack is None and self.persona is None and self.food is None


def plan_import_drops(paths: list[Path]) -> ImportDropPlan:
    """
    拖放判定：
    - 含立绘 / 图集 → 新形象包（含「立绘+人设+食物」完整包）
    - 仅人设 → 当前包 人设.txt
    - 仅食物 → 当前包 食物/
    - 人设 + 食物（无立绘）→ 两者写入当前包
    """
    plan = ImportDropPlan()
    existing = [Path(p).resolve() for p in paths if Path(p).exists()]
    if not existing:
        return plan

    pack_paths: list[Path] = []
    persona_sources: list[Path] = []
    food_sources: list[Path] = []

    for path in existing:
        kinds = _kinds_for_path(path)
        if "pack" in kinds:
            pack_paths.append(path)
        if "persona" in kinds:
            src = resolve_persona_source(path)
            if src:
                persona_sources.append(src)
        if "food" in kinds:
            src = resolve_food_source(path)
            if src:
                food_sources.append(src)

    if pack_paths:
        plan.pack = pack_paths[0]
        return plan

    if persona_sources:
        plan.persona = persona_sources[0]
    if food_sources:
        plan.food = food_sources[0]
    return plan


def can_accept_import_drop(paths: list[Path]) -> bool:
    return not plan_import_drops(paths).is_empty()
