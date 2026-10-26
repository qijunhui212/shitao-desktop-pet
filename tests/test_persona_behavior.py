"""Tests for persona [行为] parsing."""

from __future__ import annotations

from datetime import datetime

from brain import persona_behavior as pb
from brain.persona_behavior import (
    in_time_window,
    parse_behavior_text,
    pick_idle_behavior,
    pick_startup_behavior,
)
from pet.pack_prompt import split_persona_content


def test_split_persona_content():
    raw = "你是小猫。\n\n[行为]\n[早安 06:00-11:00]\n早上好"
    chat, behavior = split_persona_content(raw)
    assert "你是小猫" in chat
    assert behavior is not None
    assert "早安" in behavior


def test_parse_morning_rule():
    script = parse_behavior_text(
        "[早安 07:00-10:00 每天]\n早安主人\n今天也要开心"
    )
    assert len(script.rules) == 1
    assert script.rules[0].trigger == "morning"
    assert script.rules[0].daily is True
    assert script.rules[0].lines == ["早安主人", "今天也要开心"]


def test_pick_morning_with_mock_script(monkeypatch):
    script = parse_behavior_text("[早安 06:00-23:59 每天]\n早安呀")
    monkeypatch.setattr(pb, "get_behavior_script", lambda **_: script)
    text, key = pick_startup_behavior(
        hours_away=0,
        now=datetime(2026, 5, 20, 8, 0, 0),
        fired_today=set(),
    )
    assert text == "早安呀"
    assert key is not None


def test_morning_not_repeat_same_day(monkeypatch):
    script = parse_behavior_text("[早安 06:00-23:59 每天]\n早安呀")
    monkeypatch.setattr(pb, "get_behavior_script", lambda **_: script)
    rule_key = script.rules[0].rule_key
    text, key = pick_startup_behavior(
        hours_away=0,
        now=datetime(2026, 5, 20, 8, 0, 0),
        fired_today={rule_key},
    )
    assert text is None


def test_pick_idle_from_script(monkeypatch):
    script = parse_behavior_text("[陪伴]\n在忙吗\n")
    monkeypatch.setattr(pb, "get_behavior_script", lambda **_: script)
    assert pick_idle_behavior() == "在忙吗"


def test_in_time_window_cross_midnight():
    start = datetime(2026, 5, 20, 23, 0).time()
    end = datetime(2026, 5, 20, 5, 0).time()
    assert in_time_window(datetime(2026, 5, 20, 23, 30), start, end)
    assert in_time_window(datetime(2026, 5, 20, 4, 0), start, end)
    assert not in_time_window(datetime(2026, 5, 20, 12, 0), start, end)
