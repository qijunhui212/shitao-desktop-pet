"""Tests for companion greeting helpers."""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from brain.companion_greeting import (
    companion_days_label,
    hours_since,
    idle_bubble_text,
    load_pack_greeting_lines,
    startup_greeting_text,
)
from memory.companion import CompanionStore
from memory.store import MemoryStore


def test_startup_greeting_long_away():
    text = startup_greeting_text(hours_away=48, user_name="小明")
    assert "小明" in text


def test_idle_bubble_has_content():
    text = idle_bubble_text()
    assert len(text) >= 4


def test_hours_since():
    past = (datetime.now() - timedelta(hours=3)).isoformat(timespec="seconds")
    assert hours_since(past) >= 2.5


def test_companion_days_label():
    first = datetime.now().isoformat(timespec="seconds")
    assert "陪伴" in companion_days_label(first)


def test_load_pack_greetings_from_file(tmp_path: Path):
    pack = tmp_path / "demo"
    pack.mkdir()
    (pack / "greetings.txt").write_text("# comment\nhello\n", encoding="utf-8")
    lines = load_pack_greeting_lines(pack)
    assert lines == ["hello"]


def test_companion_store_touch_open(tmp_path: Path, monkeypatch):
    db = tmp_path / "test.db"
    monkeypatch.setattr("memory.store.DB_PATH", db)
    store = MemoryStore()
    companion = CompanionStore(store)
    assert companion.touch_open() == 0.0
    hours = companion.touch_open()
    assert hours >= 0.0
    assert companion.chat_count() == 0
    companion.touch_chat()
    assert companion.chat_count() == 1
    store.close()
