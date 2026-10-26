"""从人设文件 [行为] 段解析主动陪伴规则。"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from datetime import datetime, time
from pathlib import Path

from config.character_config import resolve_character_dir
from pet.pack_prompt import find_pack_prompt_file, split_persona_content
BEHAVIOR_FILENAMES = ("行为.txt", "behavior.txt", "状态.txt")

MORNING_TRIGGERS = frozenset({"早安", "早上", "morning"})
NIGHT_TRIGGERS = frozenset({"晚安", "夜间", "night"})
RETURN_TRIGGERS = frozenset({"久别", "重逢", "return", "回来"})
IDLE_TRIGGERS = frozenset({"陪伴", "随机", "idle", "气泡"})
STARTUP_TRIGGERS = frozenset({"启动", "打开", "startup", "开场"})

_TIME_RANGE_RE = re.compile(
    r"(\d{1,2}:\d{2})\s*[-~到至]\s*(\d{1,2}:\d{2})"
)
_HOURS_RE = re.compile(
    r"(?:hours?\s*>=\s*|>=\s*|超过\s*)?(\d+(?:\.\d+)?)\s*(?:小时|h|hr|hrs)\b",
    re.IGNORECASE,
)
_HEADER_RE = re.compile(r"^\s*\[(?P<body>[^\]]+)\]\s*$")

_script_cache: tuple[str, "BehaviorScript | None"] | None = None


@dataclass
class BehaviorRule:
    trigger: str
    lines: list[str] = field(default_factory=list)
    time_start: time | None = None
    time_end: time | None = None
    hours_min: float | None = None
    daily: bool = False
    rule_key: str = ""


@dataclass
class BehaviorScript:
    rules: list[BehaviorRule] = field(default_factory=list)

    def rules_for(self, trigger: str) -> list[BehaviorRule]:
        return [r for r in self.rules if r.trigger == trigger]


def invalidate_behavior_script() -> None:
    global _script_cache
    _script_cache = None


def _parse_clock(value: str) -> time | None:
    value = value.strip()
    match = re.match(r"^(\d{1,2}):(\d{2})$", value)
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if 0 <= hour <= 23 and 0 <= minute <= 59:
        return time(hour, minute)
    return None


def _normalize_trigger(token: str) -> str:
    t = token.strip().lower()
    if t in MORNING_TRIGGERS or token in MORNING_TRIGGERS:
        return "morning"
    if t in NIGHT_TRIGGERS or token in NIGHT_TRIGGERS:
        return "night"
    if t in RETURN_TRIGGERS or token in RETURN_TRIGGERS:
        return "return"
    if t in IDLE_TRIGGERS or token in IDLE_TRIGGERS:
        return "idle"
    if t in STARTUP_TRIGGERS or token in STARTUP_TRIGGERS:
        return "startup"
    return "startup"


def _parse_header(body: str) -> BehaviorRule:
    parts = body.split()
    trigger_token = parts[0] if parts else "启动"
    rule = BehaviorRule(trigger=_normalize_trigger(trigger_token))
    rest = " ".join(parts[1:])

    if rule.trigger == "morning" and not rest:
        rule.time_start, rule.time_end = time(6, 0), time(11, 0)
        rule.daily = True
    elif rule.trigger == "night" and not rest:
        rule.time_start, rule.time_end = time(21, 0), time(5, 0)
        rule.daily = True

    for match in _TIME_RANGE_RE.finditer(body):
        start = _parse_clock(match.group(1))
        end = _parse_clock(match.group(2))
        if start and end:
            rule.time_start, rule.time_end = start, end

    hours_match = _HOURS_RE.search(body)
    if hours_match:
        rule.hours_min = float(hours_match.group(1))

    if rule.trigger == "return" and rule.hours_min is None:
        rule.hours_min = 1.0

    if any(k in body for k in ("每天", "daily", "每日", "一次")):
        rule.daily = True
    if rule.trigger in ("morning", "night") and rule.time_start:
        rule.daily = True

    rule.rule_key = f"{rule.trigger}:{body.strip()}"
    return rule


def parse_behavior_text(text: str) -> BehaviorScript:
    rules: list[BehaviorRule] = []
    current: BehaviorRule | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        header = _HEADER_RE.match(line)
        if header:
            if current and current.lines:
                rules.append(current)
            current = _parse_header(header.group("body"))
            continue
        if line.startswith("时间") and ":" in line:
            if current:
                window = line.split(":", 1)[1]
                match = _TIME_RANGE_RE.search(window)
                if match:
                    start = _parse_clock(match.group(1))
                    end = _parse_clock(match.group(2))
                    if start and end:
                        current.time_start, current.time_end = start, end
            continue
        if line.startswith("频率") and current:
            if any(k in line for k in ("每天", "daily", "每日")):
                current.daily = True
            continue
        if current is None:
            continue
        current.lines.append(line)

    if current and current.lines:
        rules.append(current)
    return BehaviorScript(rules=rules)


def _read_behavior_sidecar(root: Path) -> str | None:
    for name in BEHAVIOR_FILENAMES:
        path = root / name
        if not path.is_file():
            continue
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            continue
    return None


def load_behavior_script(pack_dir: Path | None = None) -> BehaviorScript | None:
    root = pack_dir if pack_dir is not None else resolve_character_dir()
    if not root or not root.is_dir():
        return None

    chunks: list[str] = []
    prompt_path = find_pack_prompt_file(root)
    if prompt_path and prompt_path.is_file():
        try:
            raw = prompt_path.read_text(encoding="utf-8")
            _, behavior = split_persona_content(raw)
            if behavior:
                chunks.append(behavior)
        except OSError:
            pass

    sidecar = _read_behavior_sidecar(root)
    if sidecar:
        chunks.append(sidecar)

    if not chunks:
        return None
    script = parse_behavior_text("\n\n".join(chunks))
    return script if script.rules else None


def get_behavior_script(*, force_refresh: bool = False) -> BehaviorScript | None:
    global _script_cache
    root = resolve_character_dir()
    cache_key = str(root.resolve()) if root and root.is_dir() else ""
    if not force_refresh and _script_cache and _script_cache[0] == cache_key:
        return _script_cache[1]

    script = load_behavior_script(root)
    _script_cache = (cache_key, script)
    return script


def in_time_window(now: datetime, start: time | None, end: time | None) -> bool:
    if start is None or end is None:
        return True
    current = now.time()
    if start <= end:
        return start <= current <= end
    return current >= start or current <= end


def _apply_name(text: str, user_name: str) -> str:
    prefix = f"{user_name}，" if user_name else ""
    if prefix and not text.startswith(user_name):
        return prefix + text
    return text


def _pick_line(rule: BehaviorRule, *, user_name: str = "") -> str:
    line = random.choice(rule.lines)
    return _apply_name(line, user_name)


def _rule_matches_return(rule: BehaviorRule, hours_away: float) -> bool:
    threshold = rule.hours_min if rule.hours_min is not None else 1.0
    return hours_away >= threshold


def pick_startup_behavior(
    *,
    hours_away: float,
    user_name: str = "",
    now: datetime | None = None,
    fired_today: set[str] | None = None,
) -> tuple[str | None, str | None]:
    """返回 (台词, rule_key)；无匹配时 (None, None)。"""
    script = get_behavior_script()
    if not script:
        return None, None
    now = now or datetime.now()
    fired = fired_today or set()

    for rule in script.rules_for("morning"):
        if not in_time_window(now, rule.time_start, rule.time_end):
            continue
        if rule.daily and rule.rule_key in fired:
            continue
        return _pick_line(rule, user_name=user_name), rule.rule_key

    for rule in script.rules_for("return"):
        if not _rule_matches_return(rule, hours_away):
            continue
        if rule.daily and rule.rule_key in fired:
            continue
        return _pick_line(rule, user_name=user_name), rule.rule_key

    for rule in script.rules_for("night"):
        if not in_time_window(now, rule.time_start, rule.time_end):
            continue
        if rule.daily and rule.rule_key in fired:
            continue
        return _pick_line(rule, user_name=user_name), rule.rule_key

    for rule in script.rules_for("startup"):
        if rule.daily and rule.rule_key in fired:
            continue
        return _pick_line(rule, user_name=user_name), rule.rule_key

    return None, None


def pick_idle_behavior(*, user_name: str = "") -> str | None:
    script = get_behavior_script()
    if not script:
        return None
    idle_rules = script.rules_for("idle")
    if not idle_rules:
        return None
    rule = random.choice(idle_rules)
    return _pick_line(rule, user_name=user_name)


def pick_scheduled_behavior(
    *,
    user_name: str = "",
    now: datetime | None = None,
    fired_today: set[str] | None = None,
) -> tuple[str | None, str | None]:
    """运行中定时检查：仅匹配需 daily 的早安/晚安段。"""
    script = get_behavior_script()
    if not script:
        return None, None
    now = now or datetime.now()
    fired = fired_today or set()

    for trigger in ("morning", "night"):
        for rule in script.rules_for(trigger):
            if not rule.daily:
                continue
            if not in_time_window(now, rule.time_start, rule.time_end):
                continue
            if rule.rule_key in fired:
                continue
            return _pick_line(rule, user_name=user_name), rule.rule_key
    return None, None
