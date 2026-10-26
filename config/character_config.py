"""Parse character pack path and per-sprite triggers from .env."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from config.paths import resource_root
from config.settings import ROOT

# 形象/子文件夹（打包后在 _internal/形象 或 exe 同级的 形象/）
CHARACTER_ROOT = resource_root() / os.getenv("CHARACTER_ROOT", "形象")
CHARACTER_PACK = os.getenv("CHARACTER_PACK", "银杰动漫形象").strip()
CHARACTER_MAX_HEIGHT = int(os.getenv("CHARACTER_MAX_HEIGHT", "220"))
CHARACTER_SIZE_MIN = 60
CHARACTER_SIZE_MAX = 420
MOOD_SWITCH_MS = int(os.getenv("MOOD_SWITCH_MS", "4500"))


def clamp_character_height(value: int) -> int:
    return max(CHARACTER_SIZE_MIN, min(CHARACTER_SIZE_MAX, int(value)))

# GIF: auto=有 gif 就播 | on=强制 gif | off=只用 PNG
CHARACTER_USE_GIF = os.getenv("CHARACTER_USE_GIF", "auto").strip().lower()


class Trigger(str, Enum):
    HOVER = "hover"
    RANDOM = "random"
    DRAG = "drag"

    @classmethod
    def parse(cls, value: str) -> Trigger:
        v = value.strip().lower()
        if v in ("hover", "mouse", "悬停", "鼠标", "触碰", "触摸", "指针"):
            return cls.HOVER
        if v in ("drag", "拖动", "拖拽", "拉着", "拽"):
            return cls.DRAG
        return cls.RANDOM


# 仅匹配「用户操作」相关词；动作语义（打招呼、跳等）不算，一律进随机池
_HOVER_HINTS = (
    "hover",
    "mouse",
    "mouseover",
    "mouseenter",
    "cursor",
    "pointer",
    "悬停",
    "鼠标",
    "指针",
    "移入",
    "靠近",
    "触碰",
    "触摸",
    "掠过",
)
_DRAG_HINTS = (
    "drag",
    "dragging",
    "拖动",
    "拖拽",
    "拽",
    "拖行",
    "拉着",
    "抓住",
    "拎着",
)
def infer_trigger_from_stem(stem: str) -> Trigger:
    """根据文件名猜测触发：悬停/拖动；其余（含走动、运动）进随机池。"""
    lower = stem.lower()
    for hint in _DRAG_HINTS:
        if hint in lower or hint in stem:
            return Trigger.DRAG
    for hint in _HOVER_HINTS:
        if hint in lower or hint in stem:
            return Trigger.HOVER
    return Trigger.RANDOM


_SKIP_MEDIA_STEMS = frozenset(
    {"persona", "prompt", "readme", "人设", "提示词", "icon", "app_icon"}
)
_MEDIA_SUFFIXES = (".png", ".gif", ".webp", ".jpg", ".jpeg", ".bmp")


@dataclass(frozen=True)
class SpriteBinding:
    name: str  # 状态名（不含扩展名）
    trigger: Trigger
    png_path: Path | None
    gif_path: Path | None

    @property
    def path(self) -> Path:
        """兼容旧代码：优先 PNG，否则 GIF。"""
        if self.png_path is not None:
            return self.png_path
        if self.gif_path is not None:
            return self.gif_path
        raise ValueError(f"no media for {self.name}")


def resolve_character_dir() -> Path | None:
    """形象/<CHARACTER_PACK>；仅按当前包名查找，避免文件夹改名后误加载其它包。"""
    if not CHARACTER_PACK:
        return None
    res = resource_root()
    candidates = [
        CHARACTER_ROOT / CHARACTER_PACK,
        res / CHARACTER_PACK,
        res / "形象" / CHARACTER_PACK,
        ROOT / CHARACTER_PACK,
        ROOT / "形象" / CHARACTER_PACK,
    ]
    seen: set[Path] = set()
    for path in candidates:
        p = path.resolve()
        if p in seen:
            continue
        seen.add(p)
        if p.is_dir():
            return p
    return None


def list_character_packs() -> list[str]:
    """列出 形象/ 下所有子文件夹名。"""
    if not CHARACTER_ROOT.is_dir():
        return []
    return sorted(
        d.name for d in CHARACTER_ROOT.iterdir() if d.is_dir() and not d.name.startswith(".")
    )


def _list_pack_media_stems(dir_path: Path) -> list[str]:
    """形象包内所有立绘文件名（不含扩展名），无需固定命名。"""
    stems: set[str] = set()
    for pattern in ("*.png", "*.gif", "*.webp", "*.jpg", "*.jpeg", "*.bmp"):
        for p in dir_path.glob(pattern):
            if p.is_file() and not p.name.startswith("."):
                stem = p.stem
                if stem.lower() not in _SKIP_MEDIA_STEMS:
                    stems.add(stem)
    gif_dir = dir_path / "gif"
    if gif_dir.is_dir():
        for p in gif_dir.glob("*.gif"):
            if p.is_file():
                stems.add(p.stem)
    for logical in _load_gif_map(dir_path):
        if logical.lower() not in _SKIP_MEDIA_STEMS:
            stems.add(logical)
    return sorted(stems)


def _auto_discover(dir_path: Path) -> list[tuple[str, Trigger]]:
    """
    每次启动/切换形象时扫描当前包文件夹。
    无关键词 → 随机轮播；文件名含悬停/拖动等词 → 对应触发。
    """
    names = _list_pack_media_stems(dir_path)
    if not names:
        return []
    return [(name, infer_trigger_from_stem(name)) for name in names]


def _bindings_from_specs(
    dir_path: Path, specs: list[tuple[str, Trigger]]
) -> list[SpriteBinding]:
    bindings: list[SpriteBinding] = []
    for stem, trigger in specs:
        png, gif = resolve_state_media(dir_path, stem)
        if png or gif:
            bindings.append(
                SpriteBinding(
                    name=stem,
                    trigger=trigger,
                    png_path=png,
                    gif_path=gif,
                )
            )
    return bindings


def _load_gif_map(dir_path: Path) -> dict[str, str]:
    """可选：gif_map.json 将状态名映射到 gif/ 下文件名。"""
    map_file = dir_path / "gif_map.json"
    if not map_file.is_file():
        return {}
    try:
        data = json.loads(map_file.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def resolve_state_media(dir_path: Path, name: str) -> tuple[Path | None, Path | None]:
    """解析某状态的静态图 / GIF 路径（均可缺省其一）。"""
    png: Path | None = None
    for ext in (".png", ".webp", ".jpg", ".jpeg", ".bmp"):
        candidate = dir_path / f"{name}{ext}"
        if candidate.is_file():
            png = candidate
            break

    gif_map = _load_gif_map(dir_path)
    gif_candidates: list[Path] = []
    if name in gif_map:
        mapped = gif_map[name]
        gif_candidates.append(dir_path / "gif" / mapped)
        gif_candidates.append(dir_path / mapped)
    gif_candidates.extend(
        [
            dir_path / "gif" / f"{name}.gif",
            dir_path / f"{name}.gif",
        ]
    )
    gif: Path | None = None
    for candidate in gif_candidates:
        if candidate.is_file():
            gif = candidate
            break
    return png, gif


def prefer_gif_playback(bindings: list[SpriteBinding]) -> bool:
    mode = CHARACTER_USE_GIF
    if mode in ("0", "false", "no", "off"):
        return False
    if mode in ("1", "true", "yes", "on"):
        return True
    return any(b.gif_path is not None for b in bindings)


def resolve_companion_gif(dir_path: Path) -> Path | None:
    """gif_map「走动」或包内 走动.gif（与 移动.png 合并为同一随机动作时用）。"""
    gif_map = _load_gif_map(dir_path)
    if "走动" in gif_map:
        mapped = gif_map["走动"]
        for candidate in (dir_path / "gif" / mapped, dir_path / mapped):
            if candidate.is_file():
                return candidate
    for name in ("走动.gif", "walk.gif"):
        for candidate in (dir_path / name, dir_path / "gif" / name):
            if candidate.is_file():
                return candidate
    return None


def merge_move_stem_bindings(
    dir_path: Path, bindings: list[SpriteBinding]
) -> list[SpriteBinding]:
    """移动.png + 走动.gif 合并为一个随机动作「走动」（仅原地播动画）。"""
    stems = ("移动", "走动")
    picked = [b for b in bindings if b.name in stems]
    if not picked:
        return bindings
    png: Path | None = None
    gif: Path | None = None
    for b in picked:
        if b.png_path is not None:
            png = b.png_path
        if b.gif_path is not None:
            gif = b.gif_path
    if gif is None:
        gif = resolve_companion_gif(dir_path)
    if png is None:
        for stem in stems:
            p, _ = resolve_state_media(dir_path, stem)
            if p is not None:
                png = p
                break
    rest = [b for b in bindings if b.name not in stems]
    if png is None and gif is None:
        return rest
    return rest + [
        SpriteBinding(name="走动", trigger=Trigger.RANDOM, png_path=png, gif_path=gif)
    ]


def load_sprite_bindings() -> tuple[Path | None, list[SpriteBinding]]:
    """按当前 CHARACTER_PACK 文件夹实时扫描，不依赖写死的动作名列表。"""
    dir_path = resolve_character_dir()
    if not dir_path:
        return None, []

    specs = _auto_discover(dir_path)
    bindings = _bindings_from_specs(dir_path, specs)
    bindings = merge_move_stem_bindings(dir_path, bindings)
    return dir_path, bindings
