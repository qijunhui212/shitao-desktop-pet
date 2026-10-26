from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from hashlib import sha256
import re
import time

from .models import BridgeSettings, IncomingGroupMessage


def strip_pet_mention(text: str, mention_text: str = "@师滔") -> str:
    return re.sub(re.escape(mention_text), "", text, flags=re.IGNORECASE).strip(" \t\r\n:：，,。")


def is_pet_mentioned(message: IncomingGroupMessage, mention_text: str = "@师滔") -> bool:
    if message.mention_targets_known:
        return message.is_group_mention
    return message.is_group_mention or bool(re.search(
        re.escape(mention_text) + r'(?=$|[\s:：,，。!！?？])', message.content.replace('＠', '@')))


def _stable_id(message: IncomingGroupMessage) -> str:
    raw = "\x1f".join((message.group_name, message.sender_name, message.content, message.message_id))
    return sha256(raw.encode("utf-8", "replace")).hexdigest()


@dataclass(frozen=True)
class GateResult:
    accepted: bool
    reason: str
    text: str = ""


class MessageGate:
    """Fail-closed gate: one named group, new incoming messages, explicit mention."""

    def __init__(self, settings: BridgeSettings, seen_limit: int = 512):
        self.settings = settings.validated()
        self._seen: OrderedDict[str, None] = OrderedDict()
        self._seen_limit = max(32, seen_limit)
        self._last_accepted = float("-inf")
        self._in_flight = False

    def set_in_flight(self, value: bool) -> None:
        self._in_flight = bool(value)

    def check(self, message: IncomingGroupMessage, now: float | None = None) -> GateResult:
        now = time.monotonic() if now is None else now
        if message.group_name.strip() != self.settings.group_name:
            return GateResult(False, "different_group")
        if message.is_self is not False:
            return GateResult(False, "own_message")
        content = message.content.strip()
        if not content:
            return GateResult(False, "empty_message")
        key = _stable_id(message)
        if key in self._seen:
            return GateResult(False, "duplicate")
        if self._in_flight:
            return GateResult(False, "reply_in_progress")
        if not is_pet_mentioned(message, self.settings.mention_text):
            return GateResult(False, "not_mentioned")
        if now - self._last_accepted < self.settings.cooldown_seconds:
            return GateResult(False, "cooldown")
        clean_text = message.reply_content if message.reply_content is not None else strip_pet_mention(content, self.settings.mention_text)
        if not clean_text:
            return GateResult(False, "mention_only")
        self._seen[key] = None
        while len(self._seen) > self._seen_limit:
            self._seen.popitem(last=False)
        self._last_accepted = now
        self._in_flight = True
        return GateResult(True, "accepted", clean_text[:1500])


def message_from_wxauto(msg, chat, configured_group: str) -> IncomingGroupMessage:
    """Normalize the small public Message surface used by wxauto adapters."""
    content = str(getattr(msg, "content", "") or "")
    sender = str(
        getattr(msg, "sender", "")
        or getattr(msg, "who", "")
        or getattr(msg, "nickname", "")
        or "群成员"
    )
    attr = str(getattr(msg, "attr", "") or "").lower()
    class_name = type(msg).__name__.lower()
    is_self = bool(getattr(msg, "is_self", False)) or attr in {"self", "selfmessage"} or "selfmessage" in class_name
    mention = "@师滔" in content or "＠师滔" in content
    if not mention:
        for field in ("mentions", "at_list", "mention_list", "mentioned_users"):
            value = getattr(msg, field, None)
            if value and "师滔" in str(value):
                mention = True
                break
    message_id = str(
        getattr(msg, "local_id", "")
        or getattr(msg, "msg_id", "")
        or getattr(msg, "id", "")
        or getattr(msg, "create_time", "")
    )
    return IncomingGroupMessage(
        group_name=configured_group,
        sender_name=sender,
        content=content.replace("＠", "@"),
        message_id=message_id,
        is_self=is_self,
        is_group_mention=mention,
    )


class IdleNudgePolicy:
    """One optional nudge after a quiet spell; new group activity resets it."""

    def __init__(self, idle_seconds: int = 20 * 60):
        self.idle_seconds = max(20 * 60, int(idle_seconds))
        self._last_activity = time.monotonic()
        self._sent_for_quiet_period = False

    def observe_activity(self, now: float | None = None) -> None:
        self._last_activity = time.monotonic() if now is None else now
        self._sent_for_quiet_period = False

    def observe_message(self, message: IncomingGroupMessage, now: float | None = None) -> None:
        """Only other members' messages reset the quiet timer.

        The pet's own announcement must not start a repeating 20-minute
        announcement loop.
        """
        if message.is_self is not True:
            self.observe_activity(now)

    def is_due(self, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        return (
            not self._sent_for_quiet_period
            and now - self._last_activity >= self.idle_seconds
        )

    def is_still_quiet(self, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        return now - self._last_activity >= self.idle_seconds

    def mark_sent(self) -> None:
        self._sent_for_quiet_period = True


def message_from_uia_item(main_window, item, edit_area, tools, configured_group: str) -> IncomingGroupMessage | None:
    """Normalize one visible UIA message; uncertain ownership fails closed."""
    try:
        content = str(item.window_text() or "").strip()
        if not content:
            return None
        runtime_id = getattr(getattr(item, "element_info", None), "runtime_id", "")
    except Exception:
        return None
    try:
        is_self = bool(tools.is_my_bubble(main_window, item, edit_area))
    except Exception:
        # Unknown ownership resets idle time, but the reply gate rejects it.
        is_self = None

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    sender = "群成员"
    if len(lines) > 1 and len(lines[0]) <= 40 and not lines[0].startswith(("@", "＠")):
        sender = lines[0].rstrip(":：") or sender
        content = "\n".join(lines[1:]).strip()
    return IncomingGroupMessage(
        group_name=configured_group,
        sender_name=sender,
        content=content,
        message_id=str(runtime_id or ""),
        is_self=is_self,
        is_group_mention=("@师滔" in content or "＠师滔" in content),
    )
