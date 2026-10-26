from __future__ import annotations

from collections import deque
from hashlib import sha256
from threading import Lock

from .models import IncomingGroupMessage


class GroupReplyEngine:
    """Uses the existing pet ChatService with a short, memory-only group thread."""

    def __init__(self, chat_service_factory, history_limit: int = 8):
        self._factory = chat_service_factory
        self._history = deque(maxlen=max(2, history_limit))
        self._observed_keys: set[str] = set()
        self._observed_order: deque[str] = deque()
        self._lock = Lock()

    @staticmethod
    def _message_key(message: IncomingGroupMessage) -> str:
        if message.message_id:
            return f"id:{message.group_name}:{message.message_id}"
        raw = "\x1f".join((message.group_name, message.sender_name, message.content))
        return sha256(raw.encode("utf-8", "replace")).hexdigest()

    def observe_message(self, message: IncomingGroupMessage) -> None:
        """Keep a small in-memory window of new group text for later @ replies."""
        if not message.content.strip():
            return
        key = self._message_key(message)
        with self._lock:
            if key in self._observed_keys:
                return
            self._observed_keys.add(key)
            self._observed_order.append(key)
            while len(self._observed_order) > 512:
                self._observed_keys.discard(self._observed_order.popleft())
            role = "assistant" if message.is_self is True else "user"
            content = message.content.strip()[:600]
            if role == "user":
                sender = message.sender_name.strip() or "群成员"
                content = f"{sender}: {content}"
            self._history.append({"role": role, "content": content, "_event_key": key})

    def reply(self, message: IncomingGroupMessage, text: str, cancel_event=None) -> str:
        self.observe_message(message)
        speaker = message.sender_name.strip() or "群成员"
        prompt = self._group_prompt(
            f"微信群「{message.group_name}」中，成员「{speaker}」刚才@你说：\n{text}",
            "结合前面的群聊内容，像群聊里的师滔一样直接接话，适当简短；不要声称自己掌握了未提供的消息，也不要替其他成员表态。",
        )
        key = self._message_key(message)
        with self._lock:
            context = [entry for entry in self._history if entry.get("_event_key") != key]
        return self._generate(prompt, cancel_event=cancel_event, history=context,
                              memory_scope=(message.account_id,message.group_id))

    def idle_message(self, group_name: str, cancel_event=None, memory_scope=None) -> str:
        prompt = self._group_prompt(
            f"微信群「{group_name}」已经安静了二十分钟。",
            "结合最近的群聊内容，或从你记得的共同经历、健身、学习或日常话题里自然挑一个，发一句简短、像师滔会说的话来重新开个话头。"
            "只写一条适合直接发到群里的文字，不提自动提醒、知识库或你在等待。",
        )
        return self._generate(prompt, cancel_event=cancel_event, memory_scope=memory_scope)

    def _group_prompt(self, context: str, instruction: str) -> str:
        return f"{context}\n\n{instruction}"

    def _generate(self, prompt: str, cancel_event=None, history=None, memory_scope=None) -> str:
        if history is None:
            with self._lock:
                history = list(self._history)
        context = [{"role": entry["role"], "content": entry["content"]} for entry in history]
        chat = self._factory()
        display, _reminder, _memory = chat.chat_stream(
            prompt,
            [],
            session_history=context,
            conversation_user_name="",
            persist_history=False,
            personalize_reply=False,
            group_memory_scope=memory_scope,
            should_cancel=(lambda: cancel_event.is_set()) if cancel_event else None,
        )
        with self._lock:
            self._history.append({"role": "assistant", "content": display})
        return display

