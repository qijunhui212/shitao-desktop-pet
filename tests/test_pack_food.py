"""Tests for pack food discovery."""

from __future__ import annotations

from pathlib import Path

from pet.pack_food import (
    discover_pack_foods,
    get_food_catalog,
    invalidate_food_catalog,
)


def test_discover_food_folder(tmp_path: Path):
    pack = tmp_path / "demo"
    food_dir = pack / "食物"
    food_dir.mkdir(parents=True)
    (food_dir / "寿司.png").write_bytes(b"png")
    (food_dir / "汉堡.png").write_bytes(b"png")

    items = discover_pack_foods(pack)
    assert len(items) == 2
    assert items[0].name == "寿司"
    assert items[0].image_path is not None


def test_discover_foods_txt_with_images(tmp_path: Path):
    pack = tmp_path / "demo"
    food_dir = pack / "食物"
    food_dir.mkdir(parents=True)
    (food_dir / "cake.png").write_bytes(b"png")
    (pack / "食物.txt").write_text("小蛋糕|cake.png\n", encoding="utf-8")

    items = discover_pack_foods(pack)
    assert len(items) == 1
    assert items[0].name == "小蛋糕"
    assert items[0].image_path.name == "cake.png"


def test_discover_foods_txt_name_only_uses_builtin(tmp_path: Path):
    pack = tmp_path / "demo"
    pack.mkdir()
    (pack / "foods.txt").write_text("特制鱼排\n", encoding="utf-8")

    items = discover_pack_foods(pack)
    assert len(items) == 1
    assert items[0].name == "特制鱼排"
    assert items[0].builtin_kind == 0


def test_discover_food_in_named_subfolder(tmp_path: Path):
    pack = tmp_path / "demo"
    carrot_dir = pack / "carrot"
    carrot_dir.mkdir(parents=True)
    (carrot_dir / "carrot.png").write_bytes(b"png")
    (pack / "foods.txt").write_text("carrot\n", encoding="utf-8")

    items = discover_pack_foods(pack)
    assert len(items) == 1
    assert items[0].name == "carrot"
    assert items[0].image_path is not None


def test_discover_named_subfolder_without_txt(tmp_path: Path):
    pack = tmp_path / "demo"
    folder = pack / "carrot"
    folder.mkdir(parents=True)
    (folder / "carrot.png").write_bytes(b"png")

    items = discover_pack_foods(pack)
    assert len(items) == 1
    assert items[0].name == "carrot"


def test_catalog_falls_back_to_builtin(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("pet.pack_food.resolve_character_dir", lambda: tmp_path)
    invalidate_food_catalog()
    catalog = get_food_catalog(force_refresh=True)
    assert len(catalog) == 5
    assert catalog[0].name == "鱼"
