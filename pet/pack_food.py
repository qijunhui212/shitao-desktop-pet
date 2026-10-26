"""形象包内定制食物：扫描 食物/ 文件夹或 食物.txt。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config.character_config import resolve_character_dir

FOOD_DIR_NAMES = ("食物", "food", "Food")
FOOD_LIST_FILENAMES = ("foods.txt", "食物.txt")
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp")

_BUILTIN_NAMES = ("鱼", "肉", "饭", "果", "菜")
_catalog_cache: tuple[str, list["FoodDef"]] | None = None


@dataclass(frozen=True)
class FoodDef:
    key: str
    name: str
    image_path: Path | None = None
    builtin_kind: int | None = None


def _read_manifest(root: Path) -> list[tuple[str, str | None]] | None:
    for fname in FOOD_LIST_FILENAMES:
        path = root / fname
        if not path.is_file():
            continue
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            continue
        entries: list[tuple[str, str | None]] = []
        for line in raw.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if "|" in stripped:
                name, image_hint = stripped.split("|", 1)
                name = name.strip()
                image_hint = image_hint.strip() or None
            else:
                lower = stripped.lower()
                if any(lower.endswith(ext) for ext in IMAGE_EXTS):
                    image_hint = stripped
                    name = Path(stripped).stem
                else:
                    name = stripped
                    image_hint = None
            if name:
                entries.append((name, image_hint))
        return entries
    return None


def _food_subdir(root: Path) -> Path | None:
    for name in FOOD_DIR_NAMES:
        path = root / name
        if path.is_dir():
            return path
    return None


def _resolve_image(
    root: Path,
    food_dir: Path | None,
    name: str,
    image_hint: str | None,
) -> Path | None:
    candidates: list[Path] = []
    if image_hint:
        hint = Path(image_hint)
        if food_dir:
            candidates.append(food_dir / hint.name)
        candidates.append(root / hint.name)
        if not hint.is_absolute():
            candidates.append(root / hint)
            name_dir = root / name
            if name_dir.is_dir():
                candidates.append(name_dir / hint.name)
    else:
        search_dirs = [food_dir, root] if food_dir else [root]
        for folder in search_dirs:
            if not folder:
                continue
            for ext in IMAGE_EXTS:
                candidates.append(folder / f"{name}{ext}")
            for path in sorted(folder.iterdir()):
                if path.is_file() and path.stem == name:
                    candidates.append(path)
        name_dir = root / name
        if name_dir.is_dir():
            for ext in IMAGE_EXTS:
                candidates.append(name_dir / f"{name}{ext}")
            for path in sorted(name_dir.iterdir()):
                if path.is_file() and path.suffix.lower() in IMAGE_EXTS:
                    candidates.append(path)
    for path in candidates:
        if path.is_file() and path.suffix.lower() in IMAGE_EXTS:
            return path
    return None


def _scan_named_food_dirs(root: Path) -> list[FoodDef]:
    """兼容用户把每种食物放在「包/食物名/图片.png」子文件夹的情况。"""
    skip = {*FOOD_DIR_NAMES, "__pycache__"}
    items: list[FoodDef] = []
    for sub in sorted(root.iterdir()):
        if not sub.is_dir() or sub.name in skip or sub.name.startswith("."):
            continue
        image_path: Path | None = None
        for path in sorted(sub.iterdir()):
            if path.is_file() and path.suffix.lower() in IMAGE_EXTS:
                image_path = path
                break
        if image_path:
            items.append(
                FoodDef(
                    key=f"pack:{image_path.name}",
                    name=sub.name,
                    image_path=image_path,
                )
            )
    return items


def _scan_food_dir(food_dir: Path) -> list[FoodDef]:
    items: list[FoodDef] = []
    for path in sorted(food_dir.iterdir()):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTS:
            continue
        items.append(
            FoodDef(
                key=f"pack:{path.name}",
                name=path.stem,
                image_path=path,
            )
        )
    return items


def discover_pack_foods(pack_dir: Path | None = None) -> list[FoodDef]:
    root = pack_dir if pack_dir is not None else resolve_character_dir()
    if not root or not root.is_dir():
        return []

    food_dir = _food_subdir(root)
    manifest = _read_manifest(root)
    items: list[FoodDef] = []

    if manifest is not None:
        if not manifest:
            manifest = None
        else:
            for index, (name, image_hint) in enumerate(manifest):
                image_path = _resolve_image(root, food_dir, name, image_hint)
                if image_path:
                    items.append(
                        FoodDef(
                            key=f"pack:{image_path.name}",
                            name=name,
                            image_path=image_path,
                        )
                    )
                else:
                    items.append(
                        FoodDef(
                            key=f"manifest:{index}:{name}",
                            name=name,
                            builtin_kind=index % len(_BUILTIN_NAMES),
                        )
                    )
            return items

    if food_dir:
        return _scan_food_dir(food_dir)

    named = _scan_named_food_dirs(root)
    if named:
        return named
    return []


def default_builtin_foods() -> list[FoodDef]:
    return [
        FoodDef(key=f"builtin:{i}", name=name, builtin_kind=i)
        for i, name in enumerate(_BUILTIN_NAMES)
    ]


def invalidate_food_catalog() -> None:
    global _catalog_cache
    _catalog_cache = None


def get_food_catalog(*, force_refresh: bool = False) -> list[FoodDef]:
    global _catalog_cache
    root = resolve_character_dir()
    cache_key = str(root.resolve()) if root and root.is_dir() else ""
    if not force_refresh and _catalog_cache and _catalog_cache[0] == cache_key:
        return _catalog_cache[1]

    custom = discover_pack_foods(root)
    catalog = custom if custom else default_builtin_foods()
    _catalog_cache = (cache_key, catalog)
    return catalog
