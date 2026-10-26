"""Scan 形象/ for packs; match renamed folders via content signature."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path

from config.paths import app_root, resource_root
from pet.pack_prompt import find_pack_prompt_file

_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif"}


def character_library_root() -> Path:
    root = resource_root()
    lib = root / os.getenv("CHARACTER_ROOT", "形象")
    if lib.is_dir():
        return lib
    lib = app_root() / "形象"
    return lib


def list_pack_folder_names() -> list[str]:
    lib = character_library_root()
    if not lib.is_dir():
        return []
    return sorted(
        d.name
        for d in lib.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )


def pack_dir_for_name(pack_name: str) -> Path | None:
    if not pack_name.strip():
        return None
    lib = character_library_root()
    path = lib / pack_name.strip()
    return path if path.is_dir() else None


def _has_sprite_files(folder: Path) -> bool:
    if not folder.is_dir():
        return False
    if any(folder.glob("*.png")) or any(folder.glob("*.gif")):
        return True
    gif_dir = folder / "gif"
    return gif_dir.is_dir() and any(gif_dir.glob("*.gif"))


def compute_pack_signature(pack_dir: Path) -> str:
    """Stable id for a pack: 人设内容优先，否则立绘文件列表指纹。"""
    prompt = find_pack_prompt_file(pack_dir)
    if prompt and prompt.is_file():
        try:
            raw = prompt.read_text(encoding="utf-8")
        except OSError:
            raw = ""
        lines = [
            line
            for line in raw.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        text = "\n".join(lines).strip()
        if text:
            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:20]
            return f"prompt:{digest}"

    parts: list[str] = []
    for p in sorted(pack_dir.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in _IMAGE_SUFFIXES:
            continue
        try:
            st = p.stat()
            rel = p.relative_to(pack_dir).as_posix()
            parts.append(f"{rel}:{st.st_size}:{int(st.st_mtime)}")
        except OSError:
            continue
    if not parts:
        return f"empty:{pack_dir.name}"
    digest = hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()[:20]
    return f"files:{digest}"


def find_pack_name_by_signature(signature: str) -> str | None:
    if not signature:
        return None
    matches: list[str] = []
    lib = character_library_root()
    for name in list_pack_folder_names():
        path = lib / name
        if not _has_sprite_files(path):
            continue
        if compute_pack_signature(path) == signature:
            matches.append(name)
    if len(matches) == 1:
        return matches[0]
    return None


@dataclass(frozen=True)
class PackReconcileResult:
    pack_name: str
    signature: str
    updated_env: bool
    reason: str  # ok | renamed | single_fallback | missing


def reconcile_character_pack(
    *,
    write_env: bool = True,
) -> PackReconcileResult | None:
    """
    Align CHARACTER_PACK with 形象/ on disk.
    - Folder exists → refresh signature
    - Folder missing but signature matches another folder → update pack name (rename)
    - Only one valid pack → use it
    """
    from config.character_config import CHARACTER_PACK, resolve_character_dir

    lib = character_library_root()
    if not lib.is_dir():
        return None

    pack = (CHARACTER_PACK or "").strip()
    sig_env = os.getenv("CHARACTER_PACK_SIG", "").strip()
    resolved = resolve_character_dir()

    if resolved and resolved.is_dir() and _has_sprite_files(resolved):
        sig = compute_pack_signature(resolved)
        name = resolved.name
        updated = False
        if write_env and (pack != name or sig_env != sig):
            from config.env_update import update_env_file

            update_env_file(
                {"CHARACTER_PACK": name, "CHARACTER_PACK_SIG": sig}
            )
            updated = True
        return PackReconcileResult(name, sig, updated, "ok")

    if sig_env:
        found = find_pack_name_by_signature(sig_env)
        if found:
            sig = compute_pack_signature(lib / found)
            if write_env:
                _write_pack_env(found, sig)
            return PackReconcileResult(found, sig, True, "renamed")

    valid = [
        n
        for n in list_pack_folder_names()
        if _has_sprite_files(lib / n)
    ]
    if len(valid) == 1:
        name = valid[0]
        sig = compute_pack_signature(lib / name)
        if write_env:
            _write_pack_env(name, sig)
        return PackReconcileResult(name, sig, pack != name, "single_fallback")

    return PackReconcileResult(
        pack or "",
        sig_env,
        False,
        "missing",
    )


def _write_pack_env(pack_name: str, signature: str) -> None:
    from config.env_update import update_env_file
    from pet.pack_prompt import pack_has_bound_prompt

    pack_dir = pack_dir_for_name(pack_name)
    persona = "auto"
    if pack_dir and pack_has_bound_prompt(pack_dir):
        persona = "auto"
    else:
        lower = pack_name.lower()
        persona = (
            "dog"
            if any(k in lower for k in ("puppy", "小狗", "线条", "pal"))
            else "girl"
        )
    update_env_file(
        {
            "CHARACTER_PACK": pack_name,
            "CHARACTER_PACK_SIG": signature,
            "CHARACTER_PERSONA": persona,
            "CHARACTER_USE_GIF": "auto",
        }
    )
