from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile


DEFAULT_GROUP_NAME = "示例群"


@dataclass(frozen=True)
class BridgeSettings:
    """Local bridge preferences; both listening and replying start disabled."""

    group_name: str = DEFAULT_GROUP_NAME
    listening_enabled: bool = False
    auto_reply_enabled: bool = False
    idle_announcement_enabled: bool = False
    mention_text: str = "@师滔"
    cooldown_seconds: int = 15
    hourly_memory_enabled: bool = True

    def validated(self) -> "BridgeSettings":
        group = self.group_name.strip()
        mention = self.mention_text.strip()
        if not group or len(group) > 100:
            raise ValueError("群名称需要填写，且不能超过 100 个字符。")
        if mention != "@师滔":
            raise ValueError("当前版本只响应明确提到 @师滔 的消息。")
        if not 5 <= int(self.cooldown_seconds) <= 300:
            raise ValueError("回复间隔需要在 5～300 秒之间。")
        return BridgeSettings(
            group_name=group,
            listening_enabled=bool(self.listening_enabled),
            auto_reply_enabled=bool(self.auto_reply_enabled),
            idle_announcement_enabled=bool(self.idle_announcement_enabled),
            mention_text=mention,
            cooldown_seconds=int(self.cooldown_seconds),
            hourly_memory_enabled=bool(self.hourly_memory_enabled),
        )

    @classmethod
    def load(cls, path: Path) -> "BridgeSettings":
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return cls()
            known = {field for field in cls.__dataclass_fields__}
            # Listening must always require an explicit start action after launch.
            raw["listening_enabled"] = False
            return cls(**{key: value for key, value in raw.items() if key in known}).validated()
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return cls()

    def save(self, path: Path) -> None:
        value = asdict(self.validated())
        value["listening_enabled"] = False
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False,
            prefix=f".{path.name}.", suffix=".tmp",
        ) as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
            temporary = Path(stream.name)
        temporary.replace(path)


@dataclass(frozen=True)
class IncomingGroupMessage:
    group_name: str
    sender_name: str
    content: str
    message_id: str = ""
    # None means the UI adapter could not reliably identify bubble ownership.
    is_self: bool | None = False
    is_group_mention: bool = False
    mention_targets_known: bool = False
    reply_content: str | None = None
    account_id: str = ''
    group_id: str = ''
    sender_id: str = ''
    sent_at: float = 0

