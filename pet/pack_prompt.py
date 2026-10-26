"""Per-pack persona prompt bundled with character sprites."""

from __future__ import annotations

from pathlib import Path
import re

from config.character_config import resolve_character_dir

# 形象包内任选其一（按优先级）
PROMPT_FILENAMES = (
    "persona.txt",
    "prompt.txt",
    "人设.txt",
    "提示词.txt",
    "character.txt",
)

MAX_PROMPT_CHARS = 12_000


def split_persona_content(raw: str) -> tuple[str, str | None]:
    """Keep optional local behavior scripts out of the model persona prompt."""
    parts = re.split(r'^\s*\[(?:行为|behavior)\]\s*$', raw, maxsplit=1, flags=re.M | re.I)
    return parts[0].strip(), parts[1].strip() if len(parts) == 2 else None


def find_pack_prompt_file(pack_dir: Path | None = None) -> Path | None:
    root = pack_dir if pack_dir is not None else resolve_character_dir()
    if not root or not root.is_dir():
        return None
    for name in PROMPT_FILENAMES:
        path = root / name
        if path.is_file():
            return path
    return None


def load_pack_persona_prompt(pack_dir: Path | None = None) -> str | None:
    path = find_pack_prompt_file(pack_dir)
    if not path:
        return None
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    raw, _behavior = split_persona_content(raw)
    lines = [
        line
        for line in raw.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    text = "\n".join(lines).strip()
    if not text:
        return None
    if len(text) > MAX_PROMPT_CHARS:
        text = text[:MAX_PROMPT_CHARS] + "\n…（人设文件过长已截断）"
    return text


def pack_has_bound_prompt(pack_dir: Path | None = None) -> bool:
    return load_pack_persona_prompt(pack_dir) is not None


def format_pack_prompt(template: str, pet_name: str) -> str:
    return (
        template.replace("{name}", pet_name)
        .replace("{pet_name}", pet_name)
        .replace("{宠物名}", pet_name)
    )
