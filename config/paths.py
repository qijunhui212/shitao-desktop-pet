"""Application root — correct for source checkout and PyInstaller builds."""

from __future__ import annotations

import sys
from pathlib import Path


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def app_root() -> Path:
    """Writable folder: .env, data/ beside the exe when distributed."""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def resource_root() -> Path:
    """Read-only bundled assets (形象/, assets/). PyInstaller puts them in _internal/."""
    base = app_root()
    if not is_frozen():
        return base
    internal = base / "_internal"
    if internal.is_dir():
        if (internal / "形象").is_dir() or (internal / "assets").is_dir():
            return internal
    if (base / "形象").is_dir() or (base / "assets").is_dir():
        return base
    return base


def resolve_resource_path(relative: str) -> Path:
    """Resolve a project-relative path to an existing file or directory."""
    raw = relative.strip()
    if not raw:
        return app_root() / raw
    p = Path(raw)
    if p.is_absolute():
        return p
    for root in (resource_root(), app_root()):
        cand = root / p
        if cand.exists():
            return cand
    return app_root() / p
