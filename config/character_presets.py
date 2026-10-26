"""Character presets discovered from 形象/<folder>/ (not hardcoded)."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from config.pack_discovery import (
    character_library_root,
    list_pack_folder_names,
    pack_dir_for_name,
)
from config.paths import resolve_resource_path
from config.settings import ROOT


@dataclass(frozen=True)
class CharacterPreset:
    id: str
    title: str
    subtitle: str
    display_name: str
    persona: str  # auto | dog | girl | custom
    pack: str = ""
    states: str = ""
    matte: str = ""
    use_gif: str = ""
    icon_source: str = ""


def _read_pack_meta(pack_dir: Path) -> dict:
    for name in ("pack.meta.json", "pack.json"):
        path = pack_dir / name
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            continue
    return {}


def _infer_subtitle(pack_dir: Path) -> str:
    if (pack_dir / "gif").is_dir() and any((pack_dir / "gif").glob("*.gif")):
        return "2D 形象包 · GIF"
    if any(pack_dir.glob("*.gif")):
        return "2D 形象包 · GIF"
    n_png = len(list(pack_dir.glob("*.png")))
    if n_png:
        return f"2D 形象包 · {n_png} 张 PNG"
    return "2D 形象包"


def _infer_persona(pack_name: str, pack_dir: Path) -> str:
    from pet.pack_prompt import pack_has_bound_prompt

    if pack_has_bound_prompt(pack_dir):
        return "auto"
    meta = _read_pack_meta(pack_dir)
    p = str(meta.get("persona", "")).strip().lower()
    if p in ("dog", "girl", "auto", "custom"):
        return p
    lower = pack_name.lower()
    if any(k in lower for k in ("puppy", "小狗", "线条", "pal")):
        return "dog"
    return "girl"


def preset_from_pack_folder(pack_name: str) -> CharacterPreset | None:
    pack_dir = pack_dir_for_name(pack_name)
    if pack_dir is None:
        return None
    meta = _read_pack_meta(pack_dir)
    title = str(meta.get("title", "")).strip() or pack_name
    subtitle = str(meta.get("subtitle", "")).strip() or _infer_subtitle(pack_dir)
    display = str(meta.get("display_name", "")).strip() or pack_name
    persona = _infer_persona(pack_name, pack_dir)
    icon = str(meta.get("icon", meta.get("icon_source", ""))).strip()
    matte = str(meta.get("matte", "")).strip()
    use_gif = str(meta.get("use_gif", "")).strip() or "auto"
    return CharacterPreset(
        id=f"pack:{pack_name}",
        title=title if len(title) <= 24 else title[:23] + "…",
        subtitle=subtitle,
        display_name=display,
        persona=persona,
        pack=pack_name,
        matte=matte,
        use_gif=use_gif,
        icon_source=icon,
    )


def all_presets() -> list[CharacterPreset]:
    """形象/ 下每个有效子文件夹一套预设。"""
    presets: list[CharacterPreset] = []
    for name in list_pack_folder_names():
        p = preset_from_pack_folder(name)
        if p is not None:
            presets.append(p)
    return presets


def preset_by_id(preset_id: str) -> CharacterPreset | None:
    for p in all_presets():
        if p.id == preset_id:
            return p
    return None


def detect_current_preset_id() -> str | None:
    pack = os.getenv("CHARACTER_PACK", "").strip()
    if not pack:
        return None
    for p in all_presets():
        if p.pack == pack:
            return p.id
    if pack_dir_for_name(pack):
        return f"pack:{pack}"
    return None


def preset_to_env(preset: CharacterPreset) -> dict[str, str]:
    from config.pack_discovery import compute_pack_signature, pack_dir_for_name

    pack_dir = pack_dir_for_name(preset.pack)
    env: dict[str, str] = {
        "CHARACTER_PACK": preset.pack,
        "CHARACTER_PERSONA": preset.persona,
        "CHARACTER_USE_GIF": preset.use_gif or "auto",
    }
    if preset.matte:
        env["CHARACTER_MATTE"] = preset.matte
    if preset.icon_source:
        env["APP_ICON_SOURCE"] = preset.icon_source
    if pack_dir:
        env["CHARACTER_PACK_SIG"] = compute_pack_signature(pack_dir)
    return env


def preview_image_path(preset: CharacterPreset) -> Path | None:
    pack_dir = pack_dir_for_name(preset.pack)
    if pack_dir is None:
        return None
    if preset.icon_source:
        p = resolve_resource_path(preset.icon_source)
        if p.is_file():
            return p
    for pattern in ("*.png", "gif/*.png", "*.gif", "gif/*.gif"):
        hits = sorted(pack_dir.glob(pattern))
        if hits:
            return hits[0]
    return None
