import json
import re
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ReminderAction:
    title: str
    datetime: str


@dataclass
class MemoryAction:
    user_name: str | None = None
    memory: str | None = None


def _extract_json_line(text: str, prefix: str) -> dict | None:
    """Parse JSON from a line like REMINDER_JSON: {...}."""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith(prefix):
            continue
        payload = stripped[len(prefix) :].strip()
        if not payload.startswith("{"):
            continue
        try:
            return json.loads(payload)
        except json.JSONDecodeError:
            depth = 0
            start = payload.find("{")
            if start < 0:
                continue
            for i in range(start, len(payload)):
                if payload[i] == "{":
                    depth += 1
                elif payload[i] == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(payload[start : i + 1])
                        except json.JSONDecodeError:
                            break
    match = re.search(
        re.escape(prefix) + r"\s*(\{.*\})\s*$",
        text,
        re.DOTALL | re.MULTILINE,
    )
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return None


def parse_actions(text: str) -> tuple[str, ReminderAction | None, MemoryAction | None]:
    """Strip JSON action lines from model reply and parse them."""
    reminder = None
    memory = None
    display = text

    rem_data = _extract_json_line(text, "REMINDER_JSON:")
    if rem_data and "title" in rem_data and "datetime" in rem_data:
        reminder = ReminderAction(
            title=str(rem_data["title"]),
            datetime=str(rem_data["datetime"]),
        )
        display = re.sub(
            r"^\s*REMINDER_JSON:.*$", "", display, flags=re.MULTILINE
        ).strip()

    mem_data = _extract_json_line(text, "MEMORY_JSON:")
    if mem_data:
        memory = MemoryAction(
            user_name=mem_data.get("user_name"),
            memory=mem_data.get("memory"),
        )
        display = re.sub(
            r"^\s*MEMORY_JSON:.*$", "", display, flags=re.MULTILINE
        ).strip()

    display = re.sub(r"\n{3,}", "\n\n", display).strip()
    return display, reminder, memory


def format_reminders_for_prompt(reminders: list[dict]) -> str:
    if not reminders:
        return "当前没有待执行的提醒。"
    lines = []
    for r in reminders:
        lines.append(f"- id={r['id']} 「{r['title']}」于 {r['trigger_at']}")
    return "用户待执行的提醒：\n" + "\n".join(lines)


def validate_reminder_datetime(dt_str: str) -> datetime | None:
    try:
        from dateutil import parser as date_parser

        dt = date_parser.parse(dt_str)
        if dt.tzinfo:
            dt = dt.replace(tzinfo=None)
        return dt
    except (ValueError, TypeError):
        return None
