"""Tests for import drop classification."""

from __future__ import annotations

from pathlib import Path

from pet.pack_import_classify import plan_import_drops


def test_persona_txt_only(tmp_path: Path):
    txt = tmp_path / "人设.txt"
    txt.write_text("你是小猫", encoding="utf-8")
    plan = plan_import_drops([txt])
    assert plan.pack is None
    assert plan.persona == txt
    assert plan.food is None


def test_food_folder_only(tmp_path: Path):
    food = tmp_path / "myfoods"
    food.mkdir()
    (food / "carrot.png").write_bytes(b"x")
    plan = plan_import_drops([food])
    assert plan.pack is None
    assert plan.persona is None
    assert plan.food == food


def test_full_pack_folder(tmp_path: Path):
    pack = tmp_path / "rabbit"
    pack.mkdir()
    (pack / "站立.png").write_bytes(b"x")
    (pack / "开心.png").write_bytes(b"y")
    (pack / "人设.txt").write_text("兔子", encoding="utf-8")
    food = pack / "食物"
    food.mkdir()
    (food / "carrot.png").write_bytes(b"z")
    plan = plan_import_drops([pack])
    assert plan.pack == pack
    assert plan.persona is None
    assert plan.food is None


def test_persona_and_food_no_sprites(tmp_path: Path):
    pack = tmp_path / "patch"
    pack.mkdir()
    (pack / "人设.txt").write_text("补丁", encoding="utf-8")
    food = pack / "食物"
    food.mkdir()
    (food / "carrot.png").write_bytes(b"z")
    plan = plan_import_drops([pack])
    assert plan.pack is None
    assert plan.persona == pack / "人设.txt"
    assert plan.food == pack


def test_multi_drop_pack_wins(tmp_path: Path):
    pack = tmp_path / "char"
    pack.mkdir()
    (pack / "a.png").write_bytes(b"x")
    (pack / "b.png").write_bytes(b"y")
    txt = tmp_path / "人设.txt"
    txt.write_text("x", encoding="utf-8")
    food = tmp_path / "foods"
    food.mkdir()
    (food / "f.png").write_bytes(b"z")
    plan = plan_import_drops([txt, food, pack])
    assert plan.pack == pack
    assert plan.persona is None
    assert plan.food is None
