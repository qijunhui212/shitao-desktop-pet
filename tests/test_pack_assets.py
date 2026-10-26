"""Tests for pack asset install helpers."""

from __future__ import annotations

from pathlib import Path

from pet.pack_assets import install_food_folder, install_persona_file


def test_install_persona(tmp_path: Path):
    pack = tmp_path / "demo"
    pack.mkdir()
    src = tmp_path / "p.txt"
    src.write_text("你是小猫", encoding="utf-8")
    ok, msg = install_persona_file(pack, src)
    assert ok
    assert (pack / "人设.txt").read_text(encoding="utf-8") == "你是小猫"


def test_install_food_folder(tmp_path: Path):
    pack = tmp_path / "demo"
    pack.mkdir()
    (pack / "食物.txt").write_text("旧清单\n", encoding="utf-8")
    src = tmp_path / "foods"
    src.mkdir()
    (src / "carrot.png").write_bytes(b"x")
    ok, msg, n = install_food_folder(pack, src)
    assert ok and n == 1
    assert (pack / "食物" / "carrot.png").is_file()
    assert not (pack / "食物.txt").exists()
